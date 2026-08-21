from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Assignment, Project
from app.services.capacity import all_person_capacities, get_conflicts

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/resources")
def resources(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    capacities = all_person_capacities(db, on_date=today)
    conflicts = get_conflicts(db, on_date=today)

    projects_by_id = {p.id: p for p in db.query(Project).all()}
    assignments = db.query(Assignment).all()

    current_assignments: dict[int, list[str]] = {}
    for pc in capacities:
        person_assignments = [
            a for a in assignments
            if a.person_id == pc.person.id and a.start_date <= today <= a.end_date
        ]
        current_assignments[pc.person.id] = [
            projects_by_id[a.project_id].name for a in person_assignments if a.project_id in projects_by_id
        ]

    return templates.TemplateResponse(request, "resources.html", {
        "capacities": capacities,
        "conflicts": conflicts,
        "current_assignments": current_assignments,
    })
