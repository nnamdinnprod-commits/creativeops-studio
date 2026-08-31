import json
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Form
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
    ProjectPhase,
    ProjectStatus,
    Recommendation,
    RecommendationKind,
    RecommendationStatus,
    SubStatus,
)
from app.services.assignment import engage_person

router = APIRouter()

DECIDED_BY = "Demo User"

_SCREEN_BY_KIND = {
    RecommendationKind.resource_reallocation: "/resources",
    RecommendationKind.production_action: "/intelligence",
    RecommendationKind.risk_intervention: "/dashboard",
    RecommendationKind.localisation_action: "/pipeline",
}


def _apply_resource_reallocation(db: Session, rec: Recommendation, payload: dict,
                                 option_label: str) -> str:
    """REVIEW_02.md P5.6: payload['options'] is the ranked set — resources.py's
    recommend_resource() overwrites it with resources.py's own computed options
    before it's ever persisted, so every field here (kind, to_person_id,
    new_deadline) is a Python fact, not something the model chose. This function's
    only job is to apply whichever option the human actually picked, which may or
    may not be the one recommended."""
    options = {opt["label"]: opt for opt in payload.get("options", [])}
    chosen = options.get(option_label)
    if chosen is None:
        return f"'{option_label}' is not one of this recommendation's options — no change applied."

    # REVIEW_02.md P3: computed_facts_json carries the exact assignment_id captured
    # when the recommendation was generated (resources.py's _build_conflict_facts) —
    # the one Python already knew about, not a guess re-derived from (project_id,
    # person_id), which is ambiguous once a person can hold more than one
    # assignment on the same project.
    facts = json.loads(rec.computed_facts_json)
    assignment = db.get(Assignment, facts.get("assignment_id"))
    if assignment is None:
        return "Could not find the original assignment — no change applied."

    from_person = db.get(Person, facts["overloaded_person"]["id"])

    if chosen["kind"] == "move_delivery":
        project = db.get(Project, assignment.project_id)
        new_deadline = date.fromisoformat(chosen["new_deadline"])
        shift = (new_deadline - project.deadline).days
        project.deadline = new_deadline
        assignment.start_date += timedelta(days=shift)
        assignment.end_date += timedelta(days=shift)
        db.flush()
        return (
            f"Moved '{project.name}' delivery to {new_deadline.strftime('%d %b')}, "
            f"shifting {from_person.name}'s assignment to match — a client conversation "
            f"about the new date is still needed."
        )

    # reassign (internal) and engage_external both move the same assignment to a
    # new person — engage_external routes it through engage_person() so an
    # external candidate is re-checked for capacity and lead time at accept time,
    # not just when the recommendation was first generated.
    to_person = db.get(Person, chosen["to_person_id"])
    if to_person is None:
        return "The chosen person is no longer on record — no change applied."

    if chosen["kind"] == "engage_external":
        # REVIEW_02.md P5.6: the option's own start_date/end_date, already
        # lead-time-adjusted when this option was computed (resources.py's
        # _build_conflict_facts) — not the original assignment's dates, which may
        # start before this candidate could actually begin.
        new_assignment, refusal = engage_person(
            db, to_person, project_id=assignment.project_id,
            start_date=date.fromisoformat(chosen["start_date"]),
            end_date=date.fromisoformat(chosen["end_date"]),
            allocation_pct=assignment.allocation_pct,
            role_on_project=to_person.role.value, project_phase_id=assignment.project_phase_id,
            existing_id=assignment.id,
        )
        if new_assignment is None:
            return f"Could not engage {to_person.name}: {refusal}"
        assignment = new_assignment
    else:
        assignment.person_id = to_person.id

    # The Assignment row is the source of truth for capacity, but a phase-derived
    # one also has a denormalized ProjectPhase.assigned_person_id (set by
    # assign_phase() for /timeline's own display) that this same move must keep in
    # sync — otherwise Timeline keeps showing the person this recommendation just
    # moved the work away from.
    if assignment.project_phase_id is not None:
        phase = db.get(ProjectPhase, assignment.project_phase_id)
        if phase is not None:
            phase.assigned_person_id = to_person.id

    db.flush()
    return f"{chosen['action']} — reassigned from {from_person.name} to {to_person.name}."


def _apply_production_action(db: Session, rec: Recommendation, payload: dict) -> str:
    """DATA_MODEL.md: accepting creates a Project at status ready, its
    Deliverables, the Assignment, and the Localisation row, in one transaction."""
    facts = json.loads(rec.computed_facts_json)
    brand = facts.get("brand", "Fotomera")
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
def accept(rec_id: int, option_label: str = Form(""), db: Session = Depends(get_db)):
    rec = db.get(Recommendation, rec_id)
    if rec is None or rec.status != RecommendationStatus.pending:
        return RedirectResponse(url="/resources", status_code=303)

    payload = json.loads(rec.payload_json)

    if rec.kind == RecommendationKind.resource_reallocation:
        # REVIEW_02.md P5.6: a ranked set of options, not a single action — accept
        # needs to know which one was chosen. Falls back to the recommended option
        # if the form somehow didn't send one, rather than refusing outright.
        chosen_label = option_label or payload.get("recommended_label", "")
        outcome = _apply_resource_reallocation(db, rec, payload, chosen_label)
    elif rec.kind == RecommendationKind.production_action:
        outcome = _apply_production_action(db, rec, payload)
    else:
        outcome = "No handler implemented yet for this recommendation kind."

    rec.status = RecommendationStatus.accepted
    rec.decided_by = DECIDED_BY
    rec.decided_at = datetime.now(UTC)
    rec.outcome_note = outcome
    db.commit()

    return RedirectResponse(url=_SCREEN_BY_KIND.get(rec.kind, "/resources"), status_code=303)


@router.post("/recommendations/{rec_id}/reject")
def reject(rec_id: int, db: Session = Depends(get_db)):
    rec = db.get(Recommendation, rec_id)
    if rec is not None and rec.status == RecommendationStatus.pending:
        rec.status = RecommendationStatus.rejected
        rec.decided_by = DECIDED_BY
        rec.decided_at = datetime.now(UTC)
        rec.outcome_note = "Rejected — no change applied."
        db.commit()
        return RedirectResponse(url=_SCREEN_BY_KIND.get(rec.kind, "/resources"), status_code=303)

    return RedirectResponse(url="/resources", status_code=303)
