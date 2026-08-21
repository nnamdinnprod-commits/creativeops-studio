import json
from datetime import date, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Assignment,
    Deliverable,
    DeliverableStatus,
    DeliverableType,
    Localisation,
    LocalisationStatus,
    Person,
    PersonRole,
    Priority,
    Project,
    ProjectStatus,
    Recommendation,
    RecommendationKind,
    RecommendationStatus,
    SubStatus,
)

router = APIRouter()

DECIDED_BY = "Demo User"

_SCREEN_BY_KIND = {
    RecommendationKind.resource_reallocation: "/resources",
    RecommendationKind.production_action: "/intelligence",
    RecommendationKind.risk_intervention: "/dashboard",
    RecommendationKind.localisation_action: "/pipeline",
}


def _apply_resource_reallocation(db: Session, payload: dict) -> str:
    assignment = (
        db.query(Assignment)
        .filter_by(project_id=payload["project_id"], person_id=payload["from_person_id"])
        .first()
    )
    if assignment is None:
        return "Could not find the original assignment — no change applied."

    from_person = db.get(Person, payload["from_person_id"])
    to_person = db.get(Person, payload["to_person_id"])
    assignment.person_id = payload["to_person_id"]
    db.flush()

    return f"Reassigned from {from_person.name} to {to_person.name}."


def _apply_production_action(db: Session, rec: Recommendation, payload: dict) -> str:
    """DATA_MODEL.md: accepting creates a Project at status ready, its
    Deliverables, the Assignment, and the Localisation row, in one transaction."""
    facts = json.loads(rec.computed_facts_json)
    brand = facts.get("brand", "Albelli")
    market = payload["deliverables"][0]["market"] if payload["deliverables"] else facts.get("market", "NL")

    person = db.get(Person, payload["suggested_person_id"])
    if person is None:
        return "Suggested person is no longer on record — no project created."

    start = date.fromisoformat(payload["suggested_window"]["start"])
    end = date.fromisoformat(payload["suggested_window"]["end"])
    owner = db.query(Person).filter_by(role=PersonRole.producer).first()

    project = Project(
        name=payload["recommended_action"][:80],
        brand=brand,
        campaign=f"{market} Performance Push",
        source_market=market,
        priority=Priority.medium,
        status=ProjectStatus.ready,
        deadline=end,
        owner_id=owner.id,
        brief_raw=payload["insight_summary"],
        localisation_required=payload["localisation_required"],
        estimated_days=payload["estimated_days"],
    )
    db.add(project)
    db.flush()

    for d in payload["deliverables"]:
        if d.get("type") in DeliverableType.__members__:
            db.add(Deliverable(
                project_id=project.id,
                type=DeliverableType(d["type"]),
                market=d.get("market", market),
                format_spec=d.get("format_spec"),
                status=DeliverableStatus.not_started,
                deadline=end,
            ))

    db.add(Assignment(
        project_id=project.id,
        person_id=person.id,
        allocation_pct=100,
        start_date=start,
        end_date=end,
        role_on_project=person.role.value.replace("_", " "),
    ))

    if payload["localisation_required"]:
        db.add(Localisation(
            project_id=project.id,
            target_market=market,
            language=market.lower(),
            translator_id=None,
            status=LocalisationStatus.not_started,
            review_status=SubStatus.pending,
            qa_status=SubStatus.pending,
            due_date=end,
        ))

    rec.project_id = project.id
    db.flush()

    return f"Created '{project.name}' at Ready, assigned to {person.name}."


@router.post("/recommendations/{rec_id}/accept")
def accept(rec_id: int, db: Session = Depends(get_db)):
    rec = db.get(Recommendation, rec_id)
    if rec is None or rec.status != RecommendationStatus.pending:
        return RedirectResponse(url="/resources", status_code=303)

    payload = json.loads(rec.payload_json)

    if rec.kind == RecommendationKind.resource_reallocation:
        outcome = _apply_resource_reallocation(db, payload)
    elif rec.kind == RecommendationKind.production_action:
        outcome = _apply_production_action(db, rec, payload)
    else:
        outcome = "No handler implemented yet for this recommendation kind."

    rec.status = RecommendationStatus.accepted
    rec.decided_by = DECIDED_BY
    rec.decided_at = datetime.utcnow()
    rec.outcome_note = outcome
    db.commit()

    return RedirectResponse(url=_SCREEN_BY_KIND.get(rec.kind, "/resources"), status_code=303)


@router.post("/recommendations/{rec_id}/reject")
def reject(rec_id: int, db: Session = Depends(get_db)):
    rec = db.get(Recommendation, rec_id)
    if rec is not None and rec.status == RecommendationStatus.pending:
        rec.status = RecommendationStatus.rejected
        rec.decided_by = DECIDED_BY
        rec.decided_at = datetime.utcnow()
        rec.outcome_note = "Rejected — no change applied."
        db.commit()
        return RedirectResponse(url=_SCREEN_BY_KIND.get(rec.kind, "/resources"), status_code=303)

    return RedirectResponse(url="/resources", status_code=303)
