"""Deterministic capacity math. No AI involved — every number here is arithmetic
on Assignment rows, and every number is unit tested. AI_WORKFLOWS.md explains and
recommends around these numbers; it never produces them.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Assignment, Person, Project


@dataclass
class AllocationSegment:
    """A stretch of time in which a person's total allocation is constant."""

    start: date
    end: date
    allocation_pct: int
    assignments: list[Assignment] = field(default_factory=list)


def allocation_timeline(assignments: list[Assignment]) -> list[AllocationSegment]:
    """Split a person's assignments into non-overlapping segments, each carrying
    the total allocation percentage active during that segment. This is what makes
    overlap-driven conflicts detectable, not just a person's allocation today."""
    if not assignments:
        return []

    boundaries = sorted(
        {a.start_date for a in assignments} | {a.end_date + timedelta(days=1) for a in assignments}
    )

    segments: list[AllocationSegment] = []
    for i in range(len(boundaries) - 1):
        seg_start = boundaries[i]
        seg_end = boundaries[i + 1] - timedelta(days=1)
        covering = [a for a in assignments if a.start_date <= seg_start <= a.end_date]
        if covering:
            segments.append(
                AllocationSegment(
                    start=seg_start,
                    end=seg_end,
                    allocation_pct=sum(a.allocation_pct for a in covering),
                    assignments=covering,
                )
            )
    return segments


def max_allocation_pct(assignments: list[Assignment], start: date, end: date | None = None) -> int:
    """The worst (highest) total allocation percentage active at any point in
    [start, end]. `end=None` means unbounded — "from start onward, forever."

    REVIEW_02.md P2 fix item 1: this is the one place a window-bounded peak
    allocation is computed. `peak_allocation_pct` (below) and
    app/services/assignment.py's phase-candidate check both call this rather
    than each re-deriving it from `allocation_timeline`.
    """
    segments = allocation_timeline(assignments)
    overlapping = [s for s in segments if s.end >= start and (end is None or s.start <= end)]
    return max((s.allocation_pct for s in overlapping), default=0)


def peak_allocation_pct(assignments: list[Assignment], from_date: date | None = None) -> int:
    """The worst (highest) total allocation percentage active at any point from
    `from_date` onward (defaults to today) — not just today's snapshot.

    REVIEW_02.md P2: a person who is free today but double-booked starting next
    week must read as overloaded everywhere, not just in the one place that
    happens to scan forward. This is the single definition of "how loaded is
    this person" for anything shown as a status: the Resources table, the
    dashboard's overloaded count, and the conflict list all call this, so they
    can never structurally disagree the way a today-only snapshot let them.
    """
    from_date = from_date or date.today()
    return max_allocation_pct(assignments, start=from_date)


def capacity_status(allocated_pct: int, capacity_pct: int, tight_threshold: int | None = None) -> str:
    """Overloaded when allocated exceeds contracted capacity. Tight above the
    configurable threshold (default 85, from CAPACITY_TIGHT_THRESHOLD). Otherwise
    Available. Matches docs/PRODUCT_SPEC.md's Resource & Capacity Planning rule."""
    tight_threshold = tight_threshold if tight_threshold is not None else settings.capacity_tight_threshold
    if allocated_pct > capacity_pct:
        return "overloaded"
    if allocated_pct >= tight_threshold:
        return "tight"
    return "available"


def available_pct(capacity_pct: int, allocated_pct: int) -> int:
    """Spare capacity given contracted capacity and current allocation. Trivial
    arithmetic, but named and centralised (REVIEW_02.md P2 fix item 1) so every
    caller that needs "how much room is left" reads it the same way, rather than
    re-deriving `capacity_pct - allocated_pct` inline at each call site."""
    return capacity_pct - allocated_pct


def aggregate_utilisation_pct(capacities: list["PersonCapacity"]) -> int:
    """Team-wide utilisation: total allocated as a percentage of total contracted
    capacity, rounded. Centralised here rather than in the dashboard route (P2 fix
    item 1) — it's the same class of arithmetic as everything else in this module."""
    total_capacity = sum(c.person.capacity_pct for c in capacities) or 1
    total_allocated = sum(c.allocated_pct for c in capacities)
    return round(100 * total_allocated / total_capacity)


@dataclass
class PersonCapacity:
    person: Person
    allocated_pct: int
    available_pct: int
    status: str
    next_deadline: date | None


def person_capacity(person: Person, assignments: list[Assignment], projects_by_id: dict[int, Project],
                    on_date: date | None = None) -> PersonCapacity:
    on_date = on_date or date.today()
    person_assignments = [a for a in assignments if a.person_id == person.id]
    allocated = peak_allocation_pct(person_assignments, on_date)
    status = capacity_status(allocated, person.capacity_pct)

    upcoming_deadlines = [
        projects_by_id[a.project_id].deadline
        for a in person_assignments
        if a.project_id in projects_by_id and projects_by_id[a.project_id].deadline >= on_date
    ]
    next_deadline = min(upcoming_deadlines) if upcoming_deadlines else None

    return PersonCapacity(
        person=person,
        allocated_pct=allocated,
        available_pct=available_pct(person.capacity_pct, allocated),
        status=status,
        next_deadline=next_deadline,
    )


@dataclass
class Conflict:
    person: Person
    start: date
    end: date
    allocated_pct: int
    capacity_pct: int
    projects: list[Project]


def get_conflicts(db: Session, on_date: date | None = None) -> list[Conflict]:
    """Find every person whose overlapping assignments push them over their
    contracted capacity, with the specific window and projects responsible."""
    on_date = on_date or date.today()
    people = db.query(Person).all()
    all_assignments = db.query(Assignment).all()
    projects_by_id = {p.id: p for p in db.query(Project).all()}

    conflicts: list[Conflict] = []
    for person in people:
        person_assignments = [a for a in all_assignments if a.person_id == person.id]
        for segment in allocation_timeline(person_assignments):
            if segment.end < on_date:
                continue  # conflict window already passed
            if segment.allocation_pct > person.capacity_pct:
                conflicts.append(
                    Conflict(
                        person=person,
                        start=segment.start,
                        end=segment.end,
                        allocated_pct=segment.allocation_pct,
                        capacity_pct=person.capacity_pct,
                        projects=[
                            projects_by_id[a.project_id]
                            for a in segment.assignments
                            if a.project_id in projects_by_id
                        ],
                    )
                )
    return conflicts


def all_person_capacities(db: Session, on_date: date | None = None) -> list[PersonCapacity]:
    on_date = on_date or date.today()
    people = db.query(Person).all()
    all_assignments = db.query(Assignment).all()
    projects_by_id = {p.id: p for p in db.query(Project).all()}
    return [person_capacity(p, all_assignments, projects_by_id, on_date) for p in people]
