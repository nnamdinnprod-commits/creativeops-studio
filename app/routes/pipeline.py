import json
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.templates_env import templates
from app.models import (
    Assignment,
    BriefAnalysis,
    Deliverable,
    Localisation,
    LocalisationStatus,
    Person,
    PersonRole,
    Priority,
    ProductionTempo,
    Project,
    ProjectStatus,
    Recommendation,
)
from app.services.ai.localisation import check_localisation_risk
from app.services.ai.schemas import BriefExtraction
from app.services.attention import build_attention_snapshot
from app.services.capacity import available_pct, max_allocation_pct
from app.services.localisation_risk import get_localisation_risks

# A producer coordinates rather than produces, and a translator does language work via
# the Localisation flow — neither is a plausible manual assignment to project production
# work. Same rule resources.py's reassignment candidate list already applies.
_INELIGIBLE_ASSIGNMENT_ROLES = {PersonRole.producer, PersonRole.translator}
DEFAULT_MANUAL_ASSIGNMENT_ALLOCATION_PCT = 50

LOC_STATUS_ORDER = [
    LocalisationStatus.not_started,
    LocalisationStatus.in_translation,
    LocalisationStatus.in_review,
    LocalisationStatus.qa,
    LocalisationStatus.approved,
]

router = APIRouter()

STATUS_ORDER = [
    ProjectStatus.brief,
    ProjectStatus.ready,
    ProjectStatus.assigned,
    ProjectStatus.in_production,
    ProjectStatus.creative_review,
    ProjectStatus.approved,
    ProjectStatus.delivered,
]

STATUS_LABELS = {
    ProjectStatus.brief: "Brief",
    ProjectStatus.ready: "Ready",
    ProjectStatus.assigned: "Assigned",
    ProjectStatus.in_production: "In Production",
    ProjectStatus.creative_review: "Creative Review",
    ProjectStatus.approved: "Approved",
    ProjectStatus.delivered: "Delivered",
}


def validate_transition(current: ProjectStatus, target: ProjectStatus) -> tuple[bool, str | None]:
    """REVIEW_02.md P5.3: sequence is free — any stage to any stage, forwards or
    backwards. A market re-version, a copy swap, a resize, or an artwork resend can
    legitimately go straight to Creative Review or Delivered; a sequential-only
    board can't represent that. The readiness gate (check_readiness_gate, below) is
    where "is this actually ready to skip ahead" gets enforced instead."""
    if current == target:
        return False, "Already in this status."
    return True, None


def check_readiness_gate(project: Project, target: ProjectStatus, db: Session) -> tuple[bool, str | None]:
    """PRODUCT_SPEC.md: a brief scored below the readiness threshold creates a
    project but cannot move past Ready until the gaps are filled. Only applies to
    projects that have actually been through the Brief Assistant — seed projects
    with no BriefAnalysis on record aren't gated on a score that was never computed.

    REVIEW_02.md P5.3: scoped by production_tempo — fast_track (a market re-version,
    copy swap, resize, or artwork resend) skips this entirely. standard and
    full_production both get the check below; the review only describes fast_track
    behaving differently, so there's no invented second tier of strictness."""
    if project.production_tempo == ProductionTempo.fast_track:
        return True, None
    if STATUS_ORDER.index(target) <= STATUS_ORDER.index(ProjectStatus.ready):
        return True, None
    if project.brief_analysis_id is None:
        return True, None

    analysis = db.get(BriefAnalysis, project.brief_analysis_id)
    if analysis is None or analysis.readiness_score >= settings.brief_readiness_threshold:
        return True, None

    # REVIEW_02.md P5.3: "the reason naming what is missing and what it blocks" —
    # not just the aggregate score. missing_fields_json is the same list the Brief
    # Assistant itself extracted (app/routes/brief.py), named here instead of only
    # summarised as a percentage.
    missing = json.loads(analysis.missing_fields_json)
    missing_note = f" — missing {', '.join(missing)}" if missing else ""
    return False, (
        f"Brief readiness is {analysis.readiness_score}%, below the "
        f"{settings.brief_readiness_threshold}% threshold{missing_note} — cannot move past "
        f"Ready until the gaps are filled."
    )


def _board_context(db: Session, brand: str | None, market: str | None, priority: str | None):
    query = db.query(Project)
    if brand:
        query = query.filter(Project.brand == brand)
    if market:
        query = query.filter(Project.source_market == market)
    if priority:
        query = query.filter(Project.priority == priority)
    projects = query.all()

    columns = {status: [] for status in STATUS_ORDER}
    for project in projects:
        columns[project.status].append(project)

    all_brands = sorted({p.brand for p in db.query(Project).all()})
    all_markets = sorted({p.source_market for p in db.query(Project).all()})
    people_by_id = {p.id: p for p in db.query(Person).all()}

    # Risk badges are computed live from the same signals the dashboard uses —
    # not read from Project.risk_level, which stays unpopulated in V1 rather
    # than building a separate stored-and-synced value for a demo.
    snapshot = build_attention_snapshot(db)
    project_risks = {entry["project_id"]: entry["cause"] for entry in snapshot}

    return {
        "columns": columns,
        "status_order": STATUS_ORDER,
        "status_labels": STATUS_LABELS,
        "all_statuses": STATUS_ORDER,
        "all_brands": all_brands,
        "all_markets": all_markets,
        "all_priorities": list(Priority),
        "all_tempos": list(ProductionTempo),
        "selected_brand": brand,
        "selected_market": market,
        "selected_priority": priority,
        "people_by_id": people_by_id,
        "project_risks": project_risks,
    }


@router.get("/pipeline")
def pipeline(request: Request, brand: str | None = None, market: str | None = None,
            priority: str | None = None, db: Session = Depends(get_db)):
    context = _board_context(db, brand, market, priority)
    return templates.TemplateResponse(request, "pipeline.html", context)


@router.post("/pipeline/{project_id}/status")
def change_status(project_id: int, request: Request, status: str = Form(...),
                  db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    error_message = None
    if project is None:
        error_message = "Project not found."
    else:
        try:
            target_status = ProjectStatus(status)
        except ValueError:
            target_status = None
            error_message = f"'{status}' is not a valid status."

        if target_status is not None:
            ok, reason = validate_transition(project.status, target_status)
            if ok:
                ok, reason = check_readiness_gate(project, target_status, db)
            if ok:
                project.status = target_status
                db.commit()
            else:
                error_message = reason

    context = _board_context(db, None, None, None)
    context["error_message"] = error_message
    context["error_project_id"] = project_id
    return templates.TemplateResponse(request, "partials/_board.html", context)


def _build_localisation_facts(db: Session, project_id: int, on_date: date | None = None) -> dict:
    on_date = on_date or date.today()
    flags = [f for f in get_localisation_risks(db, on_date) if f.localisation.project_id == project_id]
    return {
        "project_id": project_id,
        "at_risk": len(flags) > 0,
        "at_risk_markets": [f.localisation.target_market for f in flags],
        "reasons": [f.reason for f in flags],
        "min_days_to_due": min((f.days_to_due for f in flags), default=None),
    }


@router.get("/projects/{project_id}")
def project_detail(project_id: int, request: Request, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    owner = db.get(Person, project.owner_id)
    deliverables = db.query(Deliverable).filter_by(project_id=project.id).all()
    assignments = db.query(Assignment).filter_by(project_id=project.id).all()
    localisations = db.query(Localisation).filter_by(project_id=project.id).all()
    translators = db.query(Person).filter_by(role=PersonRole.translator).all()
    recommendations = (
        db.query(Recommendation)
        .filter_by(project_id=project.id)
        .order_by(Recommendation.created_at.desc())
        .all()
    )

    people_by_id = {p.id: p for p in db.query(Person).all()}
    assignable_people = [
        p for p in people_by_id.values() if p.role not in _INELIGIBLE_ASSIGNMENT_ROLES
    ]

    risk_assessment = None
    if localisations:
        facts = _build_localisation_facts(db, project.id)
        risk_assessment = check_localisation_risk(facts)

    brief_analysis = None
    brief_extraction = None
    if project.brief_analysis_id is not None:
        brief_analysis = db.get(BriefAnalysis, project.brief_analysis_id)
        if brief_analysis is not None:
            brief_extraction = BriefExtraction.model_validate_json(brief_analysis.extracted_json)

    return templates.TemplateResponse(request, "project_detail.html", {
        "project": project,
        "owner": owner,
        "deliverables": deliverables,
        "assignments": assignments,
        "localisations": localisations,
        "people_by_id": people_by_id,
        "translators": translators,
        "assignable_people": assignable_people,
        "default_assignment_allocation_pct": DEFAULT_MANUAL_ASSIGNMENT_ALLOCATION_PCT,
        "loc_status_order": LOC_STATUS_ORDER,
        "risk_assessment": risk_assessment,
        "brief_analysis": brief_analysis,
        "brief_extraction": brief_extraction,
        "recommendations": recommendations,
        "now": date.today(),
        "assign_resource_failed": request.query_params.get("error") == "assign_resource_failed",
    })


@router.post("/projects/{project_id}/assign")
def assign_resource(project_id: int, person_id: int = Form(...),
                    allocation_pct: int = Form(DEFAULT_MANUAL_ASSIGNMENT_ALLOCATION_PCT),
                    start_date: date = Form(...), end_date: date = Form(...),
                    db: Session = Depends(get_db)):
    """Manual whole-project assignment (project_phase_id stays None — this isn't
    derived from a schedule phase). REVIEW_02.md P3: 'Assigning a resource on the
    project page does nothing' — there was no write path here at all, only a
    read-only Assignments table. Enforces the same spare-capacity rule
    assign_phase() enforces (REVIEW_02.md P2), so a manual assign can't stack a
    person past a plausible ceiling any more than a phase assign can."""
    project = db.get(Project, project_id)
    person = db.get(Person, person_id)
    if project is None or person is None or person.role in _INELIGIBLE_ASSIGNMENT_ROLES:
        return RedirectResponse(url=f"/projects/{project_id}?error=assign_resource_failed", status_code=303)
    if end_date < start_date:
        return RedirectResponse(url=f"/projects/{project_id}?error=assign_resource_failed", status_code=303)

    # Replace this person's existing whole-project assignment on this project, the
    # same convention assign_phase() uses for a phase — never stack a second row for
    # the same (person, project) pair. Phase-derived assignments (project_phase_id
    # set) are a different thing and untouched by this action.
    existing = (
        db.query(Assignment)
        .filter_by(project_id=project_id, person_id=person_id, project_phase_id=None)
        .first()
    )
    other_assignments = [
        a for a in db.query(Assignment).filter_by(person_id=person_id).all()
        if existing is None or a.id != existing.id
    ]
    allocated = max_allocation_pct(other_assignments, start_date, end_date)
    if available_pct(person.capacity_pct, allocated) < allocation_pct:
        return RedirectResponse(url=f"/projects/{project_id}?error=assign_resource_failed", status_code=303)

    if existing is not None:
        db.delete(existing)
        db.flush()

    db.add(Assignment(
        project_id=project_id, person_id=person_id, allocation_pct=allocation_pct,
        start_date=start_date, end_date=end_date, role_on_project=person.role.value,
    ))
    db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


def _safe_return_to(return_to: str | None, default: str) -> str:
    # Only ever redirect back to a page this app itself served the form from —
    # never follow an arbitrary posted URL.
    if return_to and (return_to == "/localisation" or return_to.startswith("/localisation?")
                      or return_to.startswith("/projects/")):
        return return_to
    return default


@router.post("/localisation/{loc_id}/assign")
def assign_translator(loc_id: int, translator_id: int = Form(...),
                      return_to: str | None = Form(None), db: Session = Depends(get_db)):
    loc = db.get(Localisation, loc_id)
    if loc is not None:
        loc.translator_id = translator_id
        db.commit()
        return RedirectResponse(
            url=_safe_return_to(return_to, f"/projects/{loc.project_id}"), status_code=303)
    return RedirectResponse(url="/pipeline", status_code=303)


@router.post("/localisation/{loc_id}/advance")
def advance_localisation(loc_id: int, db: Session = Depends(get_db)):
    loc = db.get(Localisation, loc_id)
    if loc is not None:
        idx = LOC_STATUS_ORDER.index(loc.status)
        if idx < len(LOC_STATUS_ORDER) - 1:
            loc.status = LOC_STATUS_ORDER[idx + 1]
            db.commit()
        return RedirectResponse(url=f"/projects/{loc.project_id}", status_code=303)
    return RedirectResponse(url="/pipeline", status_code=303)


@router.post("/pipeline/{project_id}/priority")
def change_priority(project_id: int, request: Request, priority: str = Form(...),
                    db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    error_message = None
    if project is None:
        error_message = "Project not found."
    else:
        try:
            project.priority = Priority(priority)
            db.commit()
        except ValueError:
            error_message = f"'{priority}' is not a valid priority."

    context = _board_context(db, None, None, None)
    context["error_message"] = error_message
    context["error_project_id"] = project_id
    return templates.TemplateResponse(request, "partials/_board.html", context)


@router.post("/pipeline/{project_id}/tempo")
def change_tempo(project_id: int, request: Request, tempo: str = Form(...),
                 db: Session = Depends(get_db)):
    """REVIEW_02.md P5.3: production_tempo is what scopes the readiness gate
    (check_readiness_gate) — this is the control that sets it."""
    project = db.get(Project, project_id)
    error_message = None
    if project is None:
        error_message = "Project not found."
    else:
        try:
            project.production_tempo = ProductionTempo(tempo)
            db.commit()
        except ValueError:
            error_message = f"'{tempo}' is not a valid tempo."

    context = _board_context(db, None, None, None)
    context["error_message"] = error_message
    context["error_project_id"] = project_id
    return templates.TemplateResponse(request, "partials/_board.html", context)
