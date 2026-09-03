from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import Deliverable, PhaseKind, Person, Project, ProjectPhase, ProjectType
from app.services.ai.feasibility import assess_schedule_feasibility
from app.services.assignment import assign_phase, assigned_person_ids_by_phase, phase_candidates, unassign_phase
from app.services.assumptions import get_value
from app.services.scheduling import NOT_ASSESSED_FOR_FEASIBILITY, build_feasibility_facts
from app.services.timeline import build_timeline, conflicted_phase_ids, milestone_list

router = APIRouter()


@router.get("/timeline")
def timeline(request: Request, brand: str | None = None, market: str | None = None,
            project_type: str | None = None, owner: str | None = None, error: str | None = None,
            db: Session = Depends(get_db)):
    scheduled_ids = [row[0] for row in db.query(ProjectPhase.project_id).distinct().all()]
    scheduled_projects = db.query(Project).filter(Project.id.in_(scheduled_ids)).all()
    people_by_id = {p.id: p for p in db.query(Person).all()}

    # REVIEW_03.md item (a): an absent project reads as a bug; a stated reason
    # reads as the system knowing its own limits. Shown unfiltered — brand/
    # market/type/owner describe the chart above, not this footnote, and a
    # project with no type has no project_type_id to filter by anyway.
    unscheduled_projects = []
    for project in db.query(Project).filter(Project.project_type_id.is_(None)).order_by(Project.deadline).all():
        has_deliverables = db.query(Deliverable).filter_by(project_id=project.id).first() is not None
        reason = (
            "deliverables don't match a known project type" if has_deliverables
            else "no deliverables defined yet"
        )
        unscheduled_projects.append({"project": project, "reason": reason})

    projects = scheduled_projects
    if brand:
        projects = [p for p in projects if p.brand == brand]
    if market:
        projects = [p for p in projects if p.source_market == market]
    if project_type:
        projects = [p for p in projects if p.project_type_id == int(project_type)]
    if owner:
        projects = [p for p in projects if p.owner_id == int(owner)]

    projects_with_phases = []
    for project in sorted(projects, key=lambda p: p.deadline):
        phases = (
            db.query(ProjectPhase)
            .filter_by(project_id=project.id)
            .order_by(ProjectPhase.start_date, ProjectPhase.id)
            .all()
        )
        projects_with_phases.append((project, phases))

    context = build_timeline(projects_with_phases)
    milestones = milestone_list(projects_with_phases)

    owners = sorted(
        {people_by_id[p.owner_id] for p in scheduled_projects if p.owner_id in people_by_id},
        key=lambda person: person.name,
    )

    # REVIEW_03.md item 5: "who's assigned to this phase" is computed live from
    # Assignment rows now, not read from a stored ProjectPhase.assigned_person_id.
    all_phase_ids = [phase.id for _, phases in projects_with_phases for phase in phases]
    assigned_person_by_phase_id = assigned_person_ids_by_phase(db, all_phase_ids)

    # Only production, non-milestone phases are assignable (PLANNING.md "each production
    # phase requiring a role") — candidates are computed only for those still unassigned.
    candidates_by_phase_id = {
        phase.id: phase_candidates(db, phase)
        for _, phases in projects_with_phases
        for phase in phases
        if phase.kind == PhaseKind.production and not phase.is_milestone
        and phase.id not in assigned_person_by_phase_id
    }
    conflicted_ids = conflicted_phase_ids(candidates_by_phase_id)

    # assess_schedule_feasibility (Session B step 6) — only called for a project whose
    # schedule doesn't fit its deadline; a feasible schedule has nothing to narrate.
    # client_review_minimum_days is read live from Assumption (DECISIONS.md 027) — only
    # fetched when there's at least one scheduled project, so an empty /timeline never
    # depends on the Assumption table being seeded.
    feasibility_by_project_id = {}
    if projects_with_phases:
        client_review_minimum_days = int(get_value(db, "client_review_minimum_days"))
        for project, phases in projects_with_phases:
            if project.status in NOT_ASSESSED_FOR_FEASIBILITY:
                continue
            facts = build_feasibility_facts(phases, project.deadline,
                                            client_review_minimum_days=client_review_minimum_days)
            if not facts.get("feasible", True):
                feasibility_by_project_id[project.id] = assess_schedule_feasibility(facts)

    return templates.TemplateResponse(request, "timeline.html", {
        "timeline": context,
        "unscheduled_projects": unscheduled_projects,
        "all_brands": sorted({p.brand for p in scheduled_projects}),
        "all_markets": sorted({p.source_market for p in scheduled_projects}),
        "project_types": db.query(ProjectType).order_by(ProjectType.name).all(),
        "owners": owners,
        "selected_brand": brand,
        "selected_market": market,
        "selected_project_type": project_type,
        "selected_owner": owner,
        "has_any_schedules": len(scheduled_projects) > 0,
        "candidates_by_phase_id": candidates_by_phase_id,
        "assigned_person_by_phase_id": assigned_person_by_phase_id,
        "people_by_id": people_by_id,
        "assign_failed": error == "assign_failed",
        "feasibility_by_project_id": feasibility_by_project_id,
        "milestones": milestones,
        "conflicted_phase_ids": conflicted_ids,
    })


@router.post("/timeline/phases/{phase_id}/assign")
def assign(phase_id: int, person_id: int = Form(...), db: Session = Depends(get_db)):
    phase = db.get(ProjectPhase, phase_id)
    person = db.get(Person, person_id)
    if phase is None or person is None:
        return RedirectResponse(url="/timeline?error=assign_failed", status_code=303)

    ok, _reason = assign_phase(db, phase, person)
    if not ok:
        return RedirectResponse(url="/timeline?error=assign_failed", status_code=303)
    return RedirectResponse(url="/timeline", status_code=303)


@router.post("/timeline/phases/{phase_id}/unassign")
def unassign(phase_id: int, db: Session = Depends(get_db)):
    phase = db.get(ProjectPhase, phase_id)
    if phase is not None:
        unassign_phase(db, phase)
    return RedirectResponse(url="/timeline", status_code=303)
