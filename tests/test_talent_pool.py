"""REVIEW_02.md P5.5: external resource is a talent pool, not a permanent 0%
roster entry. Team (is_external=False) is always on the roster; a pool member
(is_external=True) only counts while an Assignment row actually covers the date
in question -- the duration of an active engagement."""

from datetime import date, timedelta

from app.models import Assignment, PersonRole, Priority, Project, ProjectStatus, Person, RateBand
from app.seed import seed_assumptions
from app.services.assignment import earliest_feasible_start, engage_person
from app.services.capacity import all_person_capacities, get_conflicts

TODAY = date(2026, 8, 21)


def _project(db_session, owner):
    project = Project(name="P1", brand="Fotomera", campaign="C", source_market="NL",
                      priority=Priority.medium, status=ProjectStatus.brief,
                      deadline=TODAY + timedelta(days=30), owner_id=owner.id, brief_raw="x")
    db_session.add(project)
    db_session.commit()
    return project


def test_earliest_feasible_start_is_today_for_an_internal_person(db_session):
    seed_assumptions(db_session)
    designer = Person(name="Dana", role=PersonRole.designer, capacity_pct=100, skills="",
                      is_external=False)
    db_session.add(designer)
    db_session.commit()
    assert earliest_feasible_start(db_session, designer, today=TODAY) == TODAY


def test_earliest_feasible_start_adds_lead_time_for_an_external_person(db_session):
    seed_assumptions(db_session)
    band = db_session.query(RateBand).filter_by(role=PersonRole.motion_designer).one()
    band.lead_time_days = 5
    db_session.commit()
    lars = Person(name="Lars", role=PersonRole.motion_designer, capacity_pct=100, skills="motion",
                 is_external=True)
    db_session.add(lars)
    db_session.commit()
    assert earliest_feasible_start(db_session, lars, today=TODAY) == TODAY + timedelta(days=5)


def test_external_person_is_off_the_roster_until_engaged(db_session):
    seed_assumptions(db_session)
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    lars = Person(name="Lars", role=PersonRole.motion_designer, capacity_pct=100, skills="motion",
                 is_external=True)
    db_session.add_all([owner, lars])
    db_session.commit()

    capacities = all_person_capacities(db_session, on_date=TODAY)
    assert lars.id not in {c.person.id for c in capacities}
    assert owner.id in {c.person.id for c in capacities}  # internal, always on roster


def test_external_person_appears_only_for_the_engagement_window(db_session):
    seed_assumptions(db_session)
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    lars = Person(name="Lars", role=PersonRole.motion_designer, capacity_pct=100, skills="motion",
                 is_external=True)
    db_session.add_all([owner, lars])
    db_session.flush()
    project = _project(db_session, owner)
    db_session.add(Assignment(project_id=project.id, person_id=lars.id, allocation_pct=100,
                              start_date=TODAY + timedelta(days=10), end_date=TODAY + timedelta(days=12)))
    db_session.commit()

    before = {c.person.id for c in all_person_capacities(db_session, on_date=TODAY)}
    during = {c.person.id for c in all_person_capacities(db_session, on_date=TODAY + timedelta(days=11))}
    after = {c.person.id for c in all_person_capacities(db_session, on_date=TODAY + timedelta(days=20))}
    assert lars.id not in before
    assert lars.id in during
    assert lars.id not in after


def test_get_conflicts_ignores_a_not_yet_engaged_external_person(db_session):
    """A stray Assignment far in the future for an unengaged pool member (or one
    whose engagement hasn't started yet) must not appear as a live conflict."""
    seed_assumptions(db_session)
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    lars = Person(name="Lars", role=PersonRole.motion_designer, capacity_pct=50, skills="motion",
                 is_external=True)
    db_session.add_all([owner, lars])
    db_session.flush()
    project = _project(db_session, owner)
    # Two overlapping assignments that WOULD overload Lars, but neither covers TODAY.
    db_session.add_all([
        Assignment(project_id=project.id, person_id=lars.id, allocation_pct=60,
                  start_date=TODAY + timedelta(days=10), end_date=TODAY + timedelta(days=15)),
        Assignment(project_id=project.id, person_id=lars.id, allocation_pct=60,
                  start_date=TODAY + timedelta(days=12), end_date=TODAY + timedelta(days=18)),
    ])
    db_session.commit()

    conflicts = get_conflicts(db_session, on_date=TODAY)
    assert lars.id not in {c.person.id for c in conflicts}


def test_engage_person_creates_an_assignment(db_session):
    seed_assumptions(db_session)
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    dana = Person(name="Dana", role=PersonRole.designer, capacity_pct=100, skills="", is_external=False)
    db_session.add_all([owner, dana])
    db_session.flush()
    project = _project(db_session, owner)
    db_session.commit()

    assignment, refusal = engage_person(
        db_session, dana, project_id=project.id, start_date=TODAY, end_date=TODAY + timedelta(days=5),
        allocation_pct=50, today=TODAY,
    )
    assert refusal is None
    assert assignment is not None
    assert assignment.person_id == dana.id and assignment.allocation_pct == 50


def test_engage_person_refuses_insufficient_capacity(db_session):
    seed_assumptions(db_session)
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    dana = Person(name="Dana", role=PersonRole.designer, capacity_pct=50, skills="", is_external=False)
    db_session.add_all([owner, dana])
    db_session.flush()
    project = _project(db_session, owner)
    db_session.add(Assignment(project_id=project.id, person_id=dana.id, allocation_pct=40,
                              start_date=TODAY, end_date=TODAY + timedelta(days=5)))
    db_session.commit()

    assignment, refusal = engage_person(
        db_session, dana, project_id=project.id, start_date=TODAY, end_date=TODAY + timedelta(days=2),
        allocation_pct=30, today=TODAY,
    )
    assert assignment is None
    assert "spare capacity" in refusal


def test_engage_person_refuses_an_external_person_starting_before_their_lead_time(db_session):
    seed_assumptions(db_session)
    band = db_session.query(RateBand).filter_by(role=PersonRole.motion_designer).one()
    band.lead_time_days = 5
    db_session.commit()
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    lars = Person(name="Lars", role=PersonRole.motion_designer, capacity_pct=100, skills="motion",
                 is_external=True)
    db_session.add_all([owner, lars])
    db_session.flush()
    project = _project(db_session, owner)
    db_session.commit()

    assignment, refusal = engage_person(
        db_session, lars, project_id=project.id, start_date=TODAY, end_date=TODAY + timedelta(days=10),
        allocation_pct=100, today=TODAY,
    )
    assert assignment is None
    assert "notice" in refusal


def test_engage_person_replaces_rather_than_stacks_when_existing_id_given(db_session):
    seed_assumptions(db_session)
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    dana = Person(name="Dana", role=PersonRole.designer, capacity_pct=100, skills="", is_external=False)
    db_session.add_all([owner, dana])
    db_session.flush()
    project = _project(db_session, owner)
    db_session.commit()

    first, _ = engage_person(db_session, dana, project_id=project.id, start_date=TODAY,
                             end_date=TODAY + timedelta(days=5), allocation_pct=30, today=TODAY)
    db_session.commit()

    second, refusal = engage_person(
        db_session, dana, project_id=project.id, start_date=TODAY, end_date=TODAY + timedelta(days=5),
        allocation_pct=60, existing_id=first.id, today=TODAY,
    )
    db_session.commit()
    assert refusal is None
    rows = db_session.query(Assignment).filter_by(project_id=project.id, person_id=dana.id).all()
    assert len(rows) == 1
    assert rows[0].allocation_pct == 60
