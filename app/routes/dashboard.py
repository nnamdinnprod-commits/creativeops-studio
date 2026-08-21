from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Localisation, LocalisationStatus, Project, ProjectStatus
from app.services.capacity import all_person_capacities, get_conflicts

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    projects = db.query(Project).all()

    conflicts = get_conflicts(db, on_date=today)
    at_risk_project_ids = {p.id for c in conflicts for p in c.projects}

    active_projects = [p for p in projects if p.status != ProjectStatus.delivered]
    at_risk_projects = [p for p in active_projects if p.id in at_risk_project_ids]
    on_track_projects = [p for p in active_projects if p.id not in at_risk_project_ids]

    upcoming_deadlines = sorted(
        (p for p in active_projects if today <= p.deadline <= today + timedelta(days=7)),
        key=lambda p: p.deadline,
    )

    capacities = all_person_capacities(db, on_date=today)
    overloaded_count = sum(1 for c in capacities if c.status == "overloaded")
    tight_count = sum(1 for c in capacities if c.status == "tight")
    total_capacity = sum(c.person.capacity_pct for c in capacities) or 1
    total_allocated = sum(c.allocated_pct for c in capacities)
    aggregate_utilisation = round(100 * total_allocated / total_capacity)

    localisation_rows = db.query(Localisation).all()
    loc_total = len(localisation_rows)
    loc_approved = sum(1 for l in localisation_rows if l.status == LocalisationStatus.approved)
    loc_pct = round(100 * loc_approved / loc_total) if loc_total else 0

    return templates.TemplateResponse(request, "dashboard.html", {
        "active_count": len(active_projects),
        "on_track_count": len(on_track_projects),
        "at_risk_count": len(at_risk_projects),
        "blocked_count": 0,
        "upcoming_deadlines": upcoming_deadlines,
        "overloaded_count": overloaded_count,
        "tight_count": tight_count,
        "aggregate_utilisation": aggregate_utilisation,
        "loc_total": loc_total,
        "loc_approved": loc_approved,
        "loc_pct": loc_pct,
    })
