"""docs/PLANNING.md 'Assignments derive from phases'. Deterministic candidate-matching and
assignment — reuses app/services/capacity.py's existing utilization math untouched, per
PLANNING.md's own promise that capacity.py "needs no rewrite, only a different source of
assignment rows." No AI involved: this is the same class of arithmetic as capacity.py and
scheduling.py, not a recommendation."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Assignment, PhaseKind, Person, ProjectPhase, RateBand
from app.services.capacity import available_pct, max_allocation_pct


def assigned_person_ids_by_phase(db: Session, phase_ids: list[int]) -> dict[int, int]:
    """REVIEW_03.md item 5: ProjectPhase.assigned_person_id used to be a stored
    mirror of "does an Assignment row exist with this project_phase_id" — kept
    in sync by three separate call sites, which is exactly the kind of thing
    that drifts (DECISIONS.md 034 already found and fixed one such drift once).
    Computed live instead: one query, no column to forget to update."""
    if not phase_ids:
        return {}
    rows = (
        db.query(Assignment.project_phase_id, Assignment.person_id)
        .filter(Assignment.project_phase_id.in_(phase_ids))
        .all()
    )
    return {phase_id: person_id for phase_id, person_id in rows}


def earliest_feasible_start(db: Session, person: Person, today: date | None = None) -> date:
    """REVIEW_02.md P5.5: the earliest date an engagement of this person could
    start — `today` for anyone on the Team, `today + lead_time_days` (RateBand, by
    role) for an external person. The one place this is computed; phase_candidates()
    and engage_person() both call it rather than re-deriving it."""
    today = today or date.today()
    if not person.is_external:
        return today
    rate_band = db.query(RateBand).filter_by(role=person.role).first()
    lead_time_days = rate_band.lead_time_days if rate_band is not None else 0
    return today + timedelta(days=lead_time_days)


def engage_person(
    db: Session, person: Person, project_id: int, start_date: date, end_date: date,
    allocation_pct: int, role_on_project: str | None = None,
    project_phase_id: int | None = None, existing_id: int | None = None,
    today: date | None = None,
) -> tuple[Assignment | None, str | None]:
    """REVIEW_02.md P5.5: "one mechanism, three screens" — the single place an
    Assignment row gets created or replaced, whichever of Timeline (assign_phase),
    the project page's manual assign, or Localisation's translator assign is doing
    the engaging. Enforces the same spare-capacity rule everywhere (REVIEW_02.md P2)
    and, for an external person, a lead-time floor on the start date: a freelancer
    cannot start tomorrow, and day rates/lead times live in the Assumptions library
    (RateBand), not on the Person row itself. Does not commit — the caller owns the
    transaction.

    `existing_id`, when given, is excluded from both the capacity check and the
    replace — re-confirming the same person to the same slot isn't rejected for
    capacity it already holds, the same convention assign_phase() already used."""
    today = today or date.today()

    other_assignments = [
        a for a in db.query(Assignment).filter_by(person_id=person.id).all()
        if existing_id is None or a.id != existing_id
    ]
    allocated = max_allocation_pct(other_assignments, start_date, end_date)
    if available_pct(person.capacity_pct, allocated) < allocation_pct:
        return None, f"{person.name} doesn't have enough spare capacity for this window."

    if person.is_external:
        earliest_start = earliest_feasible_start(db, person, today)
        if start_date < earliest_start:
            return None, (
                f"{person.name} is external and needs notice — the earliest possible "
                f"start is {earliest_start.strftime('%d %b')}."
            )

    if existing_id is not None:
        existing = db.get(Assignment, existing_id)
        if existing is not None:
            db.delete(existing)
            db.flush()

    assignment = Assignment(
        project_id=project_id, person_id=person.id, project_phase_id=project_phase_id,
        allocation_pct=allocation_pct, start_date=start_date, end_date=end_date,
        role_on_project=role_on_project or person.role.value,
    )
    db.add(assignment)
    db.flush()
    return assignment, None

# PLANNING.md doesn't specify an allocation percentage for a phase-derived assignment. 100
# (one person, fully dedicated to the phase) was the first guess, but checked against the
# actual demo roster it left phase_candidates() returning empty almost everywhere — most
# people in DEMO_DATA.md already carry a partial allocation (55%, 40%, 30%...), so requiring
# full availability made the assign-a-phase feature nearly undemonstrable. 50 — a phase is
# usually a significant piece of someone's workload, not the whole of it, matching the
# mostly-fractional allocations already used throughout this app's demo data — is the
# documented default instead. See DECISIONS.md.
PHASE_ASSIGNMENT_ALLOCATION_PCT = 50


@dataclass
class PhaseCandidate:
    person: Person
    allocated_pct: int
    available_pct: int


def phase_candidates(db: Session, phase: ProjectPhase, today: date | None = None) -> list[PhaseCandidate]:
    """People whose role matches one of the phase's required roles and who have enough
    spare capacity across the whole phase window to take it on, most-available first.

    REVIEW_02.md P5.5: "the ability to bring in external resource of any role, on
    demand" — an external person with a matching role and enough spare capacity is
    as valid a candidate as anyone on the Team, unless their role's lead time
    (RateBand, Assumptions) rules out starting by the phase's own start date.

    The lead-time check only applies to an external person. It used to run
    unconditionally, which meant an internal person — whose earliest_feasible_start
    is always just `today`, no lead time at all — was refused as a candidate for
    any phase whose start_date had already passed, a real and reachable bug: a
    phase flagged by the Blocked tile as "started, nobody assigned" is exactly a
    phase with a past start_date, and Timeline's own Assign control offered no one
    for it, internal or external, with real spare capacity sitting unused. External
    people still need the lead-time floor (engage_person() enforces the same rule
    on accept, so the two can't disagree)."""
    today = today or date.today()
    required = {r.strip() for r in phase.required_roles.split(",") if r.strip()}
    if not required:
        return []

    all_assignments = db.query(Assignment).all()
    candidates = []
    for person in db.query(Person).all():
        if person.role.value not in required:
            continue
        if person.is_external and phase.start_date < earliest_feasible_start(db, person, today):
            continue  # can't start in time — filtered before any UI ever offers it
        person_assignments = [a for a in all_assignments if a.person_id == person.id]
        allocated = max_allocation_pct(person_assignments, phase.start_date, phase.end_date)
        available = available_pct(person.capacity_pct, allocated)
        if available < PHASE_ASSIGNMENT_ALLOCATION_PCT:
            continue  # not feasible — filtered before any UI ever offers the option
        candidates.append(PhaseCandidate(person=person, allocated_pct=allocated, available_pct=available))
    return sorted(candidates, key=lambda c: -c.available_pct)


def assign_phase(db: Session, phase: ProjectPhase, person: Person) -> tuple[bool, str | None]:
    """Assigns person to phase, creating or replacing the Assignment row derived from it.
    PLANNING.md scopes this to "each production phase" — milestones are meetings, not
    assignable work, and only production-kind phases carry deliverable work. Also refuses a
    role mismatch outright, the same rule DECISIONS.md 014 fixed for the resource-
    reallocation candidate list."""
    if phase.is_milestone:
        return False, "Milestones are meetings, not assignable work."
    if phase.kind != PhaseKind.production:
        return False, f"Only production-phase work can be assigned — this is a {phase.kind.value} phase."

    required = {r.strip() for r in phase.required_roles.split(",") if r.strip()}
    if required and person.role.value not in required:
        readable = ", ".join(sorted(r.replace("_", " ") for r in required))
        return False, f"{person.name} is a {person.role.value.replace('_', ' ')}, not one of: {readable}."

    existing = db.query(Assignment).filter_by(project_phase_id=phase.id).first()

    # REVIEW_02.md P2/P5.5: engage_person() enforces spare capacity (a raw POST
    # bypassing phase_candidates()'s advisory dropdown filter must still be refused
    # here) and, for an external person, the lead-time floor on the start date.
    assignment, refusal = engage_person(
        db, person, project_id=phase.project_id, start_date=phase.start_date,
        end_date=phase.end_date, allocation_pct=PHASE_ASSIGNMENT_ALLOCATION_PCT,
        role_on_project=person.role.value, project_phase_id=phase.id,
        existing_id=existing.id if existing is not None else None,
    )
    if assignment is None:
        return False, refusal

    db.commit()
    return True, None


def unassign_phase(db: Session, phase: ProjectPhase) -> None:
    existing = db.query(Assignment).filter_by(project_phase_id=phase.id).first()
    if existing is not None:
        db.delete(existing)
    db.commit()
