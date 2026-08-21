from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from fastapi import HTTPException

from app.database import get_db
from app.models import Assignment, Deliverable, Localisation, Person, Priority, Project, ProjectStatus

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

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
    """A project may move backward freely (correcting a mistake) or forward one
    stage at a time. Skipping stages forward is refused with a reason — this is
    the operational rule the demo's Pipeline screen demonstrates."""
    if current == target:
        return False, "Already in this status."

    cur_idx = STATUS_ORDER.index(current)
    tgt_idx = STATUS_ORDER.index(target)

    if tgt_idx < cur_idx:
        return True, None

    if tgt_idx == cur_idx + 1:
        return True, None

    skipped = STATUS_ORDER[cur_idx + 1 : tgt_idx]
    skipped_names = ", ".join(STATUS_LABELS[s] for s in skipped)
    return False, (
        f"Cannot move directly from {STATUS_LABELS[current]} to {STATUS_LABELS[target]} — "
        f"must pass through {skipped_names} first."
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

    return {
        "columns": columns,
        "status_order": STATUS_ORDER,
        "status_labels": STATUS_LABELS,
        "all_statuses": STATUS_ORDER,
        "all_brands": all_brands,
        "all_markets": all_markets,
        "all_priorities": list(Priority),
        "selected_brand": brand,
        "selected_market": market,
        "selected_priority": priority,
        "people_by_id": people_by_id,
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
                project.status = target_status
                db.commit()
            else:
                error_message = reason

    context = _board_context(db, None, None, None)
    context["error_message"] = error_message
    context["error_project_id"] = project_id
    return templates.TemplateResponse(request, "partials/_board.html", context)


@router.get("/projects/{project_id}")
def project_detail(project_id: int, request: Request, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    owner = db.get(Person, project.owner_id)
    deliverables = db.query(Deliverable).filter_by(project_id=project.id).all()
    assignments = db.query(Assignment).filter_by(project_id=project.id).all()
    localisations = db.query(Localisation).filter_by(project_id=project.id).all()

    people_by_id = {p.id: p for p in db.query(Person).all()}

    return templates.TemplateResponse(request, "project_detail.html", {
        "project": project,
        "owner": owner,
        "deliverables": deliverables,
        "assignments": assignments,
        "localisations": localisations,
        "people_by_id": people_by_id,
        "now": date.today(),
    })


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
