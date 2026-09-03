import json
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Assignment,
    Deliverable,
    Person,
    PersonRole,
    Priority,
    Project,
    ProjectStatus,
    Recommendation,
    RecommendationKind,
    RecommendationStatus,
)
from app.services.assignment import engage_person
from app.services.capacity import get_conflicts
from app.services.project_creation import finalize_project

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
        # REVIEW_02.md P6.1: verified, not assumed — the shift is only "risk
        # cleared" if the overlap it targeted is actually gone.
        still_conflicted = from_person.id in {c.person.id for c in get_conflicts(db, on_date=date.today())}
        prefix = "Moved" if still_conflicted else "Risk cleared — moved"
        return (
            f"{prefix} '{project.name}' delivery to {new_deadline.strftime('%d %b')}, "
            f"shifting {from_person.name}'s assignment to match — a client conversation "
            f"about the new date is still needed."
        )

    if chosen["kind"] == "reduce_scope":
        # REVIEW_03.md R2.1: "accepting any of the three must actually apply
        # it" — the cut Deliverable rows are deleted, not just marked somehow;
        # DeliverableStatus has no "cut"/"cancelled" value, and a row left
        # sitting there in some other state would still read as work owed.
        project = db.get(Project, assignment.project_id)
        cut_ids = chosen.get("deliverable_ids") or []
        cut_deliverables = db.query(Deliverable).filter(Deliverable.id.in_(cut_ids)).all()
        dropped = sorted(f"{d.type.value.replace('_', ' ')} ({d.market})" for d in cut_deliverables)
        for deliverable in cut_deliverables:
            db.delete(deliverable)
        assignment.allocation_pct = chosen["reduced_allocation_pct"]
        db.flush()
        still_conflicted = from_person.id in {c.person.id for c in get_conflicts(db, on_date=date.today())}
        prefix = "Reduced scope" if still_conflicted else "Risk cleared — reduced scope"
        return (
            f"{prefix} on '{project.name}': dropped {', '.join(dropped) or 'the agreed deliverables'}, "
            f"{from_person.name}'s allocation on this project falls to {assignment.allocation_pct}% — "
            f"a client conversation about the smaller brief is still needed."
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

    db.flush()

    # REVIEW_02.md P6.1: "when an action resolves a risk, say so" — re-checked
    # after the fact against the same get_conflicts() the dashboard and Resources
    # use, never assumed just because a reassignment happened. from_person can
    # still be genuinely overloaded (a different conflict, untouched by this
    # accept), which is exactly why this isn't a "this always works" message.
    still_conflicted = from_person.id in {c.person.id for c in get_conflicts(db, on_date=date.today())}
    if still_conflicted:
        return f"{chosen['action']} — reassigned from {from_person.name} to {to_person.name}."
    return (
        f"Risk cleared — {chosen['action']}, reassigned from {from_person.name} to "
        f"{to_person.name}. {from_person.name} is back under {from_person.capacity_pct}% capacity."
    )


def _apply_production_action(db: Session, rec: Recommendation, payload: dict) -> str:
    """DATA_MODEL.md: accepting creates a Project at status ready, its
    Deliverables, the Assignment, and the Localisation row, in one transaction.
    Type resolution, deliverables, localisation rows, and the generated
    schedule all go through finalize_project() (REVIEW_03.md R6) — this
    function's own job is just the facts unique to a production-action accept:
    which person, which window, which brand."""
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
        # The mock's own quantity-based estimate (app/services/ai/mock.py) —
        # finalize_project() only fills this in when it's still None, so this
        # number is kept rather than overwritten by its generic schedule-span
        # fallback.
        estimated_days=payload["estimated_days"],
    )
    db.add(project)
    db.flush()

    db.add(Assignment(
        project_id=project.id,
        person_id=person.id,
        allocation_pct=100,
        start_date=start,
        end_date=end,
        role_on_project=person.role.value.replace("_", " "),
    ))

    finalize_project(
        db, project,
        deliverables=payload["deliverables"],
        localisation_targets=[market] if payload["localisation_required"] else [],
    )

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
