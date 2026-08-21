import json
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import Assignment, Person, Project, Recommendation, RecommendationKind, RecommendationStatus
from app.services.ai.resource import recommend_resource
from app.services.capacity import all_person_capacities, current_allocation_pct, get_conflicts

router = APIRouter()


def _screen_context(db: Session):
    today = date.today()
    capacities = all_person_capacities(db, on_date=today)
    conflicts = get_conflicts(db, on_date=today)

    projects_by_id = {p.id: p for p in db.query(Project).all()}
    all_assignments = db.query(Assignment).all()

    current_assignments: dict[int, list[str]] = {}
    for pc in capacities:
        person_assignments = [
            a for a in all_assignments
            if a.person_id == pc.person.id and a.start_date <= today <= a.end_date
        ]
        current_assignments[pc.person.id] = [
            projects_by_id[a.project_id].name for a in person_assignments if a.project_id in projects_by_id
        ]

    # For each conflict, the project with the soonest deadline is the one worth
    # reassigning — moving it off the overloaded person is what protects that date.
    conflict_targets = {}
    for c in conflicts:
        soonest = min(c.projects, key=lambda p: p.deadline)
        conflict_targets[c.person.id] = soonest

    recommendations = (
        db.query(Recommendation)
        .filter_by(kind=RecommendationKind.resource_reallocation)
        .order_by(Recommendation.created_at.desc())
        .all()
    )
    recommendations_view = [
        {"rec": rec, "payload": json.loads(rec.payload_json)} for rec in recommendations
    ]
    people_by_id = {p.id: p for p in db.query(Person).all()}

    return {
        "capacities": capacities,
        "conflicts": conflicts,
        "current_assignments": current_assignments,
        "conflict_targets": conflict_targets,
        "recommendations": recommendations_view,
        "people_by_id": people_by_id,
        "projects_by_id": projects_by_id,
    }


@router.get("/resources")
def resources(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "resources.html", _screen_context(db))


def _build_conflict_facts(db: Session, person_id: int, project_id: int) -> dict | None:
    today = date.today()
    overloaded = db.get(Person, person_id)
    project = db.get(Project, project_id)
    if overloaded is None or project is None:
        return None

    transfer_assignment = (
        db.query(Assignment).filter_by(person_id=person_id, project_id=project_id).first()
    )
    if transfer_assignment is None:
        return None
    transfer_pct = transfer_assignment.allocation_pct

    overloaded_assignments = db.query(Assignment).filter_by(person_id=person_id).all()
    overloaded_allocated = current_allocation_pct(overloaded_assignments, today)
    overloaded_skills = set(s.strip() for s in overloaded.skills.split(",") if s.strip())

    candidates = []
    for person in db.query(Person).all():
        if person.id == person_id:
            continue
        person_assignments = db.query(Assignment).filter_by(person_id=person.id).all()
        allocated = current_allocation_pct(person_assignments, today)
        available = person.capacity_pct - allocated
        if available < transfer_pct:
            continue  # not feasible — Python filters before the model ever sees it
        person_skills = set(s.strip() for s in person.skills.split(",") if s.strip())
        candidates.append({
            "id": person.id,
            "name": person.name,
            "role": person.role.value,
            "allocated_pct": allocated,
            "available_pct": available,
            "skills": sorted(person_skills),
            "matches_skill": bool(overloaded_skills & person_skills),
            "is_external": person.is_external,
        })

    if not candidates:
        return None

    return {
        "project_id": project.id,
        "project_name": project.name,
        "deadline": project.deadline.isoformat(),
        "overloaded_person": {
            "id": overloaded.id,
            "name": overloaded.name,
            "capacity_pct": overloaded.capacity_pct,
            "allocated_pct": overloaded_allocated,
        },
        "transfer_allocation_pct": transfer_pct,
        "candidates": candidates,
    }


@router.post("/resources/recommend")
def recommend(request: Request, person_id: int = Form(...), project_id: int = Form(...),
              db: Session = Depends(get_db)):
    facts = _build_conflict_facts(db, person_id, project_id)
    if facts is not None:
        rec = recommend_resource(facts)
        if rec is not None:
            db.add(Recommendation(
                kind=RecommendationKind.resource_reallocation,
                project_id=project_id,
                payload_json=rec.model_dump_json(),
                rationale=rec.rationale,
                computed_facts_json=json.dumps(facts, default=str),
                status=RecommendationStatus.pending,
            ))
            db.commit()
    return RedirectResponse(url="/resources", status_code=303)
