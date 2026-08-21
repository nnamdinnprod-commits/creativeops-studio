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


def current_allocation_pct(assignments: list[Assignment], on_date: date | None = None) -> int:
    """Total allocation percentage for whichever of the given assignments are
    active on `on_date` (defaults to today)."""
    on_date = on_date or date.today()
    return sum(a.allocation_pct for a in assignments if a.start_date <= on_date <= a.end_date)


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
    allocated = current_allocation_pct(person_assignments, on_date)
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
        available_pct=person.capacity_pct - allocated,
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
