"""REVIEW_02.md P5.1: project detail pages exist and work but were linked from
almost nowhere. These tests cover the call sites that needed a real behaviour
change (a route passing an id instead of a pre-joined name string), not the
purely mechanical template swaps to the shared partials/_project_ref.html macro."""

from datetime import date, timedelta

from app.models import Assignment, Person, PersonRole, Priority, Project, ProjectStatus

TODAY = date.today()  # app/routes/resources.py and localisation.py use date.today() internally


def test_resources_current_assignments_column_links_to_the_project(client, db_session):
    priya = Person(name="Priya", role=PersonRole.designer, capacity_pct=100,
                   skills="", is_external=False)
    db_session.add(priya)
    db_session.flush()

    project = Project(name="Homepage Banner Refresh", brand="Fotomera", campaign="C",
                      source_market="NL", priority=Priority.medium, status=ProjectStatus.assigned,
                      deadline=TODAY + timedelta(days=10), owner_id=priya.id, brief_raw="x")
    db_session.add(project)
    db_session.flush()
    db_session.add(Assignment(person_id=priya.id, project_id=project.id, allocation_pct=50,
                              start_date=TODAY - timedelta(days=1), end_date=TODAY + timedelta(days=5)))
    db_session.commit()

    resp = client.get("/resources")
    assert resp.status_code == 200
    assert "Homepage Banner Refresh" in resp.text
    assert f'href="/projects/{project.id}"' in resp.text


def test_resources_conflict_text_links_to_each_project(client, db_session):
    alex = Person(name="Alex", role=PersonRole.senior_designer, capacity_pct=80,
                 skills="layout", is_external=False)
    db_session.add(alex)
    db_session.flush()

    p1 = Project(name="Winter Campaign", brand="Fotomera", campaign="C", source_market="NL",
                priority=Priority.high, status=ProjectStatus.in_production,
                deadline=TODAY + timedelta(days=5), owner_id=alex.id, brief_raw="x")
    p2 = Project(name="Loyalty Teaser", brand="Fotomera", campaign="C", source_market="NL",
                priority=Priority.medium, status=ProjectStatus.assigned,
                deadline=TODAY + timedelta(days=10), owner_id=alex.id, brief_raw="x")
    db_session.add_all([p1, p2])
    db_session.flush()
    db_session.add_all([
        Assignment(person_id=alex.id, project_id=p1.id, allocation_pct=55,
                  start_date=TODAY - timedelta(days=2), end_date=TODAY + timedelta(days=5)),
        Assignment(person_id=alex.id, project_id=p2.id, allocation_pct=40,
                  start_date=TODAY - timedelta(days=1), end_date=TODAY + timedelta(days=10)),
    ])
    db_session.commit()

    resp = client.get("/resources")
    assert resp.status_code == 200
    assert f'href="/projects/{p1.id}"' in resp.text
    assert f'href="/projects/{p2.id}"' in resp.text


def test_localisation_oldest_in_queue_links_to_the_project(client, db_session):
    from app.models import Localisation, LocalisationStatus, SubStatus

    owner = Person(name="Sam", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    db_session.add(owner)
    db_session.flush()
    project = Project(name="FR Localisation Push", brand="Cassenvale", campaign="C",
                      source_market="FR", priority=Priority.medium, status=ProjectStatus.in_production,
                      deadline=TODAY + timedelta(days=10), owner_id=owner.id, brief_raw="x")
    db_session.add(project)
    db_session.flush()
    db_session.add(Localisation(project_id=project.id, target_market="ES", language="es",
                                translator_id=None, status=LocalisationStatus.in_translation,
                                review_status=SubStatus.pending, qa_status=SubStatus.pending,
                                due_date=TODAY + timedelta(days=3)))
    db_session.commit()

    resp = client.get("/localisation")
    assert resp.status_code == 200
    assert f'href="/projects/{project.id}"' in resp.text
