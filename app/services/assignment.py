"""docs/PLANNING.md 'Assignments derive from phases'. Deterministic candidate-matching and
assignment — reuses app/services/capacity.py's existing utilization math untouched, per
PLANNING.md's own promise that capacity.py "needs no rewrite, only a different source of
assignment rows." No AI involved: this is the same class of arithmetic as capacity.py and
scheduling.py, not a recommendation."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models import Assignment, PhaseKind, Person, ProjectPhase
from app.services.capacity import allocation_timeline

# PLANNING.md doesn't specify an allocation percentage for a phase-derived assignment. 100
# (one person, fully dedicated to the phase) was the first guess, but checked against the
# actual demo roster it left phase_candidates() returning empty almost everywhere — most
# people in DEMO_DATA.md already carry a partial allocation (55%, 40%, 30%...), so requiring
# full availability made the assign-a-phase feature nearly undemonstrable. 50 — a phase is
# usually a significant piece of someone's workload, not the whole of it, matching the
# mostly-fractional allocations already used throughout this app's demo data — is the
# documented default instead. See DECISIONS.md.
PHASE_ASSIGNMENT_ALLOCATION_PCT = 50


def _max_allocation_in_window(assignments: list[Assignment], start: date, end: date) -> int:
    """The worst-case (highest) total allocation percentage active at any point in
    [start, end] — not just a single snapshot date, since a phase can span days during
    which a person's other commitments start or end."""
    segments = allocation_timeline(assignments)
    overlapping = [s for s in segments if s.end >= start and s.start <= end]
    return max((s.allocation_pct for s in overlapping), default=0)


@dataclass
class PhaseCandidate:
    person: Person
    allocated_pct: int
    available_pct: int


def phase_candidates(db: Session, phase: ProjectPhase) -> list[PhaseCandidate]:
    """People whose role matches one of the phase's required roles and who have enough
    spare capacity across the whole phase window to take it on, most-available first."""
    required = {r.strip() for r in phase.required_roles.split(",") if r.strip()}
    if not required:
        return []

    all_assignments = db.query(Assignment).all()
    candidates = []
    for person in db.query(Person).all():
        if person.role.value not in required:
            continue
        person_assignments = [a for a in all_assignments if a.person_id == person.id]
        allocated = _max_allocation_in_window(person_assignments, phase.start_date, phase.end_date)
        available = person.capacity_pct - allocated
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
    if existing is not None:
        db.delete(existing)
        db.flush()

    db.add(Assignment(
        project_id=phase.project_id, person_id=person.id, project_phase_id=phase.id,
        allocation_pct=PHASE_ASSIGNMENT_ALLOCATION_PCT,
        start_date=phase.start_date, end_date=phase.end_date,
        role_on_project=person.role.value,
    ))
    phase.assigned_person_id = person.id
    db.commit()
    return True, None


def unassign_phase(db: Session, phase: ProjectPhase) -> None:
    existing = db.query(Assignment).filter_by(project_phase_id=phase.id).first()
    if existing is not None:
        db.delete(existing)
    phase.assigned_person_id = None
    db.commit()
