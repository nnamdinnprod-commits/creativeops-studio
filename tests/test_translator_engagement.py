"""REVIEW_02.md P5.5: 'Localisation translator assignment routes through this
same engagement flow -- one mechanism, three screens.'"""

from datetime import date, timedelta

from app.models import (
    Assignment,
    Localisation,
    LocalisationStatus,
    Person,
    PersonRole,
    Priority,
    Project,
    ProjectStatus,
    RateBand,
    SubStatus,
)
from app.seed import seed_assumptions
from app.services.capacity import all_person_capacities

TODAY = date.today()  # app/routes/pipeline.py's assign_translator uses date.today() internally


def _seed(db_session, due_date, lead_time_days=3):
    seed_assumptions(db_session)
    band = db_session.query(RateBand).filter_by(role=PersonRole.translator).one()
    band.lead_time_days = lead_time_days
    owner = Person(name="Sam", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    jonas = Person(name="Jonas", role=PersonRole.translator, capacity_pct=100, skills="copy_de",
                   is_external=True)
    db_session.add_all([owner, jonas])
    db_session.flush()

    project = Project(name="P1", brand="Fotomera", campaign="C", source_market="NL",
                      priority=Priority.medium, status=ProjectStatus.ready,
                      deadline=TODAY + timedelta(days=30), owner_id=owner.id, brief_raw="x")
    db_session.add(project)
    db_session.flush()

    loc = Localisation(project_id=project.id, target_market="DE", language="de",
                       translator_id=None, status=LocalisationStatus.not_started,
                       review_status=SubStatus.pending, qa_status=SubStatus.pending, due_date=due_date)
    db_session.add(loc)
    db_session.commit()
    return project, jonas, loc


def test_assigning_a_translator_creates_an_engagement_visible_in_resource_planning(client, db_session):
    project, jonas, loc = _seed(db_session, due_date=TODAY + timedelta(days=10), lead_time_days=2)

    resp = client.post(f"/localisation/{loc.id}/assign", data={"translator_id": jonas.id})
    assert resp.status_code == 200

    db_session.refresh(loc)
    assert loc.translator_id == jonas.id

    row = db_session.query(Assignment).filter_by(person_id=jonas.id, project_id=project.id).one()
    assert row.start_date == TODAY + timedelta(days=2)  # lead time pushed the start out
    assert row.end_date == loc.due_date

    on_roster = {c.person.id for c in all_person_capacities(db_session, on_date=TODAY + timedelta(days=3))}
    assert jonas.id in on_roster  # visible during the engagement, per REVIEW_02.md P5.5


def test_assigning_a_translator_is_refused_when_lead_time_leaves_no_runway(client, db_session):
    """The due date is too close for the translator's lead time -- an honest
    refusal, not a silently-started-too-early engagement."""
    project, jonas, loc = _seed(db_session, due_date=TODAY + timedelta(days=1), lead_time_days=5)

    resp = client.post(f"/localisation/{loc.id}/assign", data={"translator_id": jonas.id},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert "assign_error=" in resp.headers["location"]

    db_session.refresh(loc)
    assert loc.translator_id is None
    assert db_session.query(Assignment).filter_by(person_id=jonas.id).count() == 0


def test_assigning_an_internal_translator_starts_today_with_no_lead_time(client, db_session):
    project, jonas, loc = _seed(db_session, due_date=TODAY + timedelta(days=10))
    jonas.is_external = False
    db_session.commit()

    resp = client.post(f"/localisation/{loc.id}/assign", data={"translator_id": jonas.id})
    assert resp.status_code == 200

    row = db_session.query(Assignment).filter_by(person_id=jonas.id).one()
    assert row.start_date == TODAY


def test_assign_rejects_a_non_translator_person(client, db_session):
    project, jonas, loc = _seed(db_session, due_date=TODAY + timedelta(days=10))
    designer = Person(name="Priya", role=PersonRole.designer, capacity_pct=100, skills="", is_external=False)
    db_session.add(designer)
    db_session.commit()

    resp = client.post(f"/localisation/{loc.id}/assign", data={"translator_id": designer.id},
                       follow_redirects=False)
    assert resp.status_code == 303

    db_session.refresh(loc)
    assert loc.translator_id is None
