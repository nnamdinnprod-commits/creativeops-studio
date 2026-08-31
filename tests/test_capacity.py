from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Assignment, Person, PersonRole, Priority, Project, ProjectStatus
from app.services.capacity import (
    all_person_capacities,
    allocation_timeline,
    capacity_status,
    get_conflicts,
    max_allocation_pct,
    peak_allocation_pct,
    person_capacity,
)

TODAY = date(2026, 8, 21)


def make_assignment(person_id, project_id, allocation_pct, start_offset, end_offset):
    return Assignment(
        person_id=person_id,
        project_id=project_id,
        allocation_pct=allocation_pct,
        start_date=TODAY + timedelta(days=start_offset),
        end_date=TODAY + timedelta(days=end_offset),
    )


def test_allocation_timeline_empty():
    assert allocation_timeline([]) == []


def test_allocation_timeline_single_assignment():
    a = make_assignment(1, 1, 50, -2, 5)
    segments = allocation_timeline([a])
    assert len(segments) == 1
    assert segments[0].allocation_pct == 50
    assert segments[0].start == a.start_date
    assert segments[0].end == a.end_date


def test_allocation_timeline_overlapping_assignments_sum():
    a1 = make_assignment(1, 1, 55, -5, 0)   # today-5 .. today
    a2 = make_assignment(1, 2, 40, -3, 10)  # today-3 .. today+10
    segments = allocation_timeline([a1, a2])

    # The overlap window (today-3 .. today) should carry the combined allocation.
    overlap = [s for s in segments if s.start <= TODAY <= s.end and TODAY - timedelta(days=3) <= s.start]
    combined = [s for s in segments if s.allocation_pct == 95]
    assert combined, "expected a segment where both assignments overlap at 95%"
    assert combined[0].start == TODAY - timedelta(days=3)
    assert combined[0].end == TODAY


def test_peak_allocation_pct_finds_future_overlap_not_just_today():
    a1 = make_assignment(1, 1, 55, -5, 0)   # ended before today
    a2 = make_assignment(1, 2, 40, -3, 10)  # spans today
    a3 = make_assignment(1, 3, 60, 5, 8)    # future-only, overlaps a2
    # Today, only a2 is active (40%) — but the peak from today onward is the
    # a2+a3 overlap (100%), which a same-day snapshot would miss entirely.
    assert peak_allocation_pct([a1, a2, a3], from_date=TODAY) == 100
    # Nothing left after every assignment has ended.
    assert peak_allocation_pct([a1, a2, a3], from_date=TODAY + timedelta(days=20)) == 0


def test_max_allocation_pct_is_bounded_by_end_when_given():
    a1 = make_assignment(1, 1, 40, -3, 10)
    a2 = make_assignment(1, 2, 60, 5, 8)  # only overlaps a1 inside days 5-8
    # Window that excludes the a1+a2 overlap sees only a1's 40%.
    assert max_allocation_pct([a1, a2], start=TODAY - timedelta(days=3), end=TODAY) == 40
    # Unbounded (end=None) finds the full-timeline peak, including the overlap.
    assert max_allocation_pct([a1, a2], start=TODAY - timedelta(days=3)) == 100


def test_allocation_identical_whichever_service_path_computes_it(db_session):
    """REVIEW_02.md P2 verify: every allocation figure for the same person on the
    same date must agree, regardless of which route/service computed it — the Resources
    table (person_capacity via all_person_capacities), the conflict list (get_conflicts),
    and the raw primitive (peak_allocation_pct) must never structurally disagree."""
    alex = Person(name="Alex", role=PersonRole.senior_designer, capacity_pct=80,
                 skills="layout", is_external=False)
    db_session.add(alex)
    db_session.flush()

    p1 = Project(name="P1", brand="Fotomera", campaign="C", source_market="NL",
                priority=Priority.high, status=ProjectStatus.in_production,
                deadline=TODAY + timedelta(days=5), owner_id=alex.id, brief_raw="x")
    p2 = Project(name="P2", brand="Fotomera", campaign="C", source_market="NL",
                priority=Priority.medium, status=ProjectStatus.assigned,
                deadline=TODAY + timedelta(days=10), owner_id=alex.id, brief_raw="x")
    db_session.add_all([p1, p2])
    db_session.flush()

    # Both active today, so the "same day" figure is unambiguous across every path.
    a1 = Assignment(person_id=alex.id, project_id=p1.id, allocation_pct=55,
                    start_date=TODAY - timedelta(days=5), end_date=TODAY)
    a2 = Assignment(person_id=alex.id, project_id=p2.id, allocation_pct=40,
                    start_date=TODAY - timedelta(days=3), end_date=TODAY + timedelta(days=10))
    db_session.add_all([a1, a2])
    db_session.commit()

    from_table = next(c for c in all_person_capacities(db_session, on_date=TODAY)
                      if c.person.id == alex.id)
    from_conflicts = next(c for c in get_conflicts(db_session, on_date=TODAY)
                          if c.person.id == alex.id)
    from_primitive = peak_allocation_pct([a1, a2], from_date=TODAY)

    assert from_table.allocated_pct == from_conflicts.allocated_pct == from_primitive == 95


@pytest.mark.parametrize(
    "allocated,capacity,expected",
    [
        (95, 80, "overloaded"),
        (85, 100, "tight"),
        (90, 100, "tight"),
        (50, 100, "available"),
        (85, 85, "tight"),  # equal to capacity but not over it, and at the threshold
    ],
)
def test_capacity_status(allocated, capacity, expected):
    assert capacity_status(allocated, capacity, tight_threshold=85) == expected


def test_person_capacity_computes_available_and_next_deadline():
    person = Person(id=1, name="Alex", role=PersonRole.senior_designer, capacity_pct=100,
                    skills="layout", is_external=False)
    project = Project(id=1, name="P1", brand="Fotomera", campaign="C", source_market="NL",
                      priority=Priority.high, status=ProjectStatus.in_production,
                      deadline=TODAY + timedelta(days=5), owner_id=1, brief_raw="x")
    a1 = make_assignment(1, 1, 88, -2, 5)
    result = person_capacity(person, [a1], {1: project}, on_date=TODAY)
    assert result.allocated_pct == 88
    assert result.available_pct == 12
    assert result.status == "tight"
    assert result.next_deadline == TODAY + timedelta(days=5)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_get_conflicts_finds_overloaded_person(db_session):
    alex = Person(name="Alex", role=PersonRole.senior_designer, capacity_pct=80,
                 skills="layout", is_external=False)
    maya = Person(name="Maya", role=PersonRole.designer, capacity_pct=100,
                 skills="layout", is_external=False)
    db_session.add_all([alex, maya])
    db_session.flush()

    p1 = Project(name="P1", brand="Fotomera", campaign="C", source_market="NL",
                priority=Priority.high, status=ProjectStatus.in_production,
                deadline=TODAY + timedelta(days=5), owner_id=alex.id, brief_raw="x")
    p2 = Project(name="P2", brand="Fotomera", campaign="C", source_market="NL",
                priority=Priority.medium, status=ProjectStatus.assigned,
                deadline=TODAY + timedelta(days=10), owner_id=alex.id, brief_raw="x")
    db_session.add_all([p1, p2])
    db_session.flush()

    a1 = Assignment(person_id=alex.id, project_id=p1.id, allocation_pct=55,
                    start_date=TODAY - timedelta(days=5), end_date=TODAY)
    a2 = Assignment(person_id=alex.id, project_id=p2.id, allocation_pct=40,
                    start_date=TODAY - timedelta(days=3), end_date=TODAY + timedelta(days=10))
    a3 = Assignment(person_id=maya.id, project_id=p2.id, allocation_pct=30,
                    start_date=TODAY - timedelta(days=3), end_date=TODAY + timedelta(days=10))
    db_session.add_all([a1, a2, a3])
    db_session.commit()

    conflicts = get_conflicts(db_session, on_date=TODAY)
    conflict_people = {c.person.name for c in conflicts}
    assert "Alex" in conflict_people
    assert "Maya" not in conflict_people

    alex_conflict = next(c for c in conflicts if c.person.name == "Alex")
    assert alex_conflict.allocated_pct == 95
    assert alex_conflict.capacity_pct == 80
    project_names = {p.name for p in alex_conflict.projects}
    assert project_names == {"P1", "P2"}
