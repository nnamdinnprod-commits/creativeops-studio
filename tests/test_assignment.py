from datetime import date, timedelta

from app.models import (
    Assignment,
    PersonRole,
    PhaseKind,
    Person,
    Priority,
    Project,
    ProjectPhase,
    ProjectStatus,
)
from app.services.assignment import PHASE_ASSIGNMENT_ALLOCATION_PCT, assign_phase, phase_candidates, unassign_phase
from app.services.capacity import all_person_capacities, get_conflicts


def _project(db_session, owner):
    project = Project(name="P1", brand="Albelli", campaign="C", source_market="NL",
                      priority=Priority.medium, status=ProjectStatus.brief,
                      deadline=date(2026, 10, 1), owner_id=owner.id, brief_raw="x")
    db_session.add(project)
    db_session.commit()
    return project


def _phase(db_session, project, name="Shoot", start=date(2026, 9, 1), end=date(2026, 9, 3),
          kind=PhaseKind.production, is_milestone=False, required_roles="designer"):
    phase = ProjectPhase(project_id=project.id, name=name, kind=kind, start_date=start,
                         end_date=end, is_milestone=is_milestone, is_anchored=False,
                         required_roles=required_roles)
    db_session.add(phase)
    db_session.commit()
    return phase


def test_phase_candidates_filters_by_role(db_session):
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    designer = Person(name="Dana", role=PersonRole.designer, capacity_pct=100, skills="", is_external=False)
    copywriter = Person(name="Cara", role=PersonRole.copywriter, capacity_pct=100, skills="", is_external=False)
    db_session.add_all([owner, designer, copywriter])
    db_session.commit()

    project = _project(db_session, owner)
    phase = _phase(db_session, project, required_roles="designer")

    candidates = phase_candidates(db_session, phase)
    assert [c.person.name for c in candidates] == ["Dana"]


def test_phase_candidates_excludes_people_without_capacity_across_the_full_window(db_session):
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    designer = Person(name="Dana", role=PersonRole.designer, capacity_pct=100, skills="", is_external=False)
    db_session.add_all([owner, designer])
    db_session.commit()

    project = _project(db_session, owner)
    # Dana is free on day 1 of the phase but fully booked elsewhere starting day 2 — a
    # start-date-only check would incorrectly call her available.
    other_project = _project(db_session, owner)
    db_session.add(Assignment(project_id=other_project.id, person_id=designer.id,
                              allocation_pct=100, start_date=date(2026, 9, 2),
                              end_date=date(2026, 9, 5)))
    db_session.commit()

    phase = _phase(db_session, project, start=date(2026, 9, 1), end=date(2026, 9, 3),
                   required_roles="designer")

    candidates = phase_candidates(db_session, phase)
    assert candidates == []


def test_phase_candidates_sorted_most_available_first(db_session):
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    busy = Person(name="Busy", role=PersonRole.designer, capacity_pct=100, skills="", is_external=False)
    free = Person(name="Free", role=PersonRole.designer, capacity_pct=100, skills="", is_external=False)
    db_session.add_all([owner, busy, free])
    db_session.commit()

    project = _project(db_session, owner)
    other = _project(db_session, owner)
    db_session.add(Assignment(project_id=other.id, person_id=busy.id, allocation_pct=50,
                              start_date=date(2026, 9, 1), end_date=date(2026, 9, 3)))
    db_session.commit()

    phase = _phase(db_session, project, start=date(2026, 9, 1), end=date(2026, 9, 3))
    candidates = phase_candidates(db_session, phase)

    assert [c.person.name for c in candidates] == ["Free", "Busy"]


def test_assign_phase_refuses_milestone(db_session):
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    db_session.add(owner)
    db_session.commit()
    project = _project(db_session, owner)
    phase = _phase(db_session, project, kind=PhaseKind.review, is_milestone=True,
                   required_roles="producer")

    ok, reason = assign_phase(db_session, phase, owner)
    assert ok is False
    assert "milestone" in reason.lower()
    assert phase.assigned_person_id is None


def test_assign_phase_refuses_non_production_kind(db_session):
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    db_session.add(owner)
    db_session.commit()
    project = _project(db_session, owner)
    phase = _phase(db_session, project, kind=PhaseKind.review, required_roles="producer")

    ok, reason = assign_phase(db_session, phase, owner)
    assert ok is False
    assert "production" in reason.lower()


def test_assign_phase_refuses_role_mismatch(db_session):
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    translator = Person(name="Jonas", role=PersonRole.translator, capacity_pct=100,
                        skills="", is_external=True)
    db_session.add_all([owner, translator])
    db_session.commit()
    project = _project(db_session, owner)
    phase = _phase(db_session, project, required_roles="designer")

    ok, reason = assign_phase(db_session, phase, translator)
    assert ok is False
    assert "Jonas" in reason
    assert phase.assigned_person_id is None


def test_assign_phase_creates_assignment_that_capacity_py_picks_up_unmodified(db_session):
    """The core promise in PLANNING.md: capacity.py needs no rewrite."""
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    designer = Person(name="Dana", role=PersonRole.designer, capacity_pct=100, skills="", is_external=False)
    db_session.add_all([owner, designer])
    db_session.commit()
    project = _project(db_session, owner)
    phase = _phase(db_session, project, start=date(2026, 9, 1), end=date(2026, 9, 3),
                   required_roles="designer")

    ok, reason = assign_phase(db_session, phase, designer)
    assert ok is True and reason is None
    assert phase.assigned_person_id == designer.id

    capacities = {c.person.id: c for c in all_person_capacities(db_session, on_date=date(2026, 9, 2))}
    assert capacities[designer.id].allocated_pct == PHASE_ASSIGNMENT_ALLOCATION_PCT


def test_reassigning_a_phase_replaces_the_assignment_row_not_duplicates(db_session):
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    dana = Person(name="Dana", role=PersonRole.designer, capacity_pct=100, skills="", is_external=False)
    priya = Person(name="Priya", role=PersonRole.designer, capacity_pct=100, skills="", is_external=False)
    db_session.add_all([owner, dana, priya])
    db_session.commit()
    project = _project(db_session, owner)
    phase = _phase(db_session, project, required_roles="designer")

    assign_phase(db_session, phase, dana)
    assign_phase(db_session, phase, priya)

    matching = db_session.query(Assignment).filter_by(project_phase_id=phase.id).all()
    assert len(matching) == 1
    assert matching[0].person_id == priya.id
    assert phase.assigned_person_id == priya.id


def test_unassign_phase_removes_assignment_and_clears_person(db_session):
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    dana = Person(name="Dana", role=PersonRole.designer, capacity_pct=100, skills="", is_external=False)
    db_session.add_all([owner, dana])
    db_session.commit()
    project = _project(db_session, owner)
    phase = _phase(db_session, project, required_roles="designer")

    assign_phase(db_session, phase, dana)
    unassign_phase(db_session, phase)

    assert phase.assigned_person_id is None
    assert db_session.query(Assignment).filter_by(project_phase_id=phase.id).count() == 0


def test_overload_created_by_a_phase_assignment_is_visible_to_get_conflicts(db_session):
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    dana = Person(name="Dana", role=PersonRole.designer, capacity_pct=80, skills="", is_external=False)
    db_session.add_all([owner, dana])
    db_session.commit()
    project = _project(db_session, owner)
    # Dana already at 50% elsewhere, capacity 80 — a 100%-allocation phase assignment pushes
    # her segment total to 150%, well over capacity.
    other = _project(db_session, owner)
    db_session.add(Assignment(project_id=other.id, person_id=dana.id, allocation_pct=50,
                              start_date=date(2026, 9, 1), end_date=date(2026, 9, 5)))
    db_session.commit()
    phase = _phase(db_session, project, start=date(2026, 9, 2), end=date(2026, 9, 4),
                   required_roles="designer")

    # phase_candidates correctly excludes Dana (not enough spare capacity)...
    assert phase_candidates(db_session, phase) == []
    # ...but a direct assign (e.g. an override) still surfaces as a real conflict, since
    # capacity.py computes conflicts from whatever Assignment rows exist, unconditionally.
    assign_phase(db_session, phase, dana)
    conflicts = get_conflicts(db_session, on_date=date(2026, 9, 3))
    assert any(c.person.id == dana.id for c in conflicts)
