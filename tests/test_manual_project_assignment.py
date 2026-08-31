from datetime import date, timedelta

from app.models import Assignment, Person, PersonRole, Priority, Project, ProjectStatus

TODAY = date(2026, 8, 21)


def _seed_project(db_session):
    owner = Person(name="Sam", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    priya = Person(name="Priya", role=PersonRole.designer, capacity_pct=100, skills="", is_external=False)
    db_session.add_all([owner, priya])
    db_session.flush()

    project = Project(name="P1", brand="Fotomera", campaign="C", source_market="NL",
                      priority=Priority.medium, status=ProjectStatus.ready,
                      deadline=TODAY + timedelta(days=10), owner_id=owner.id, brief_raw="x")
    db_session.add(project)
    db_session.commit()
    return project, owner, priya


def test_assign_resource_on_project_page_persists_a_new_assignment(client, db_session):
    """REVIEW_02.md P3: 'Assigning a resource on the project page does nothing' —
    there was no write path at all, only a read-only Assignments table."""
    project, owner, priya = _seed_project(db_session)

    resp = client.post(f"/projects/{project.id}/assign",
                       data={"person_id": priya.id, "allocation_pct": 40,
                            "start_date": TODAY.isoformat(),
                            "end_date": (TODAY + timedelta(days=5)).isoformat()},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/projects/{project.id}"

    rows = db_session.query(Assignment).filter_by(project_id=project.id, person_id=priya.id).all()
    assert len(rows) == 1
    assert rows[0].allocation_pct == 40
    assert rows[0].project_phase_id is None


def test_assign_resource_replaces_rather_than_stacks_for_the_same_person(client, db_session):
    project, owner, priya = _seed_project(db_session)
    client.post(f"/projects/{project.id}/assign",
               data={"person_id": priya.id, "allocation_pct": 30,
                    "start_date": TODAY.isoformat(), "end_date": (TODAY + timedelta(days=2)).isoformat()})

    resp = client.post(f"/projects/{project.id}/assign",
                       data={"person_id": priya.id, "allocation_pct": 50,
                            "start_date": TODAY.isoformat(),
                            "end_date": (TODAY + timedelta(days=5)).isoformat()},
                       follow_redirects=False)
    assert resp.status_code == 303

    rows = db_session.query(Assignment).filter_by(project_id=project.id, person_id=priya.id).all()
    assert len(rows) == 1
    assert rows[0].allocation_pct == 50  # the second call replaced, not added to, the first


def test_assign_resource_refuses_when_not_enough_spare_capacity(client, db_session):
    """REVIEW_02.md P2's capacity guard extends here too — a manual assign can't
    stack a person past a plausible ceiling any more than a phase assign can."""
    project, owner, priya = _seed_project(db_session)
    priya.capacity_pct = 50
    other_project = Project(name="P2", brand="Fotomera", campaign="C", source_market="NL",
                            priority=Priority.medium, status=ProjectStatus.ready,
                            deadline=TODAY + timedelta(days=10), owner_id=owner.id, brief_raw="x")
    db_session.add(other_project)
    db_session.flush()
    db_session.add(Assignment(project_id=other_project.id, person_id=priya.id, allocation_pct=40,
                              start_date=TODAY, end_date=TODAY + timedelta(days=5)))
    db_session.commit()

    resp = client.post(f"/projects/{project.id}/assign",
                       data={"person_id": priya.id, "allocation_pct": 30,
                            "start_date": TODAY.isoformat(),
                            "end_date": (TODAY + timedelta(days=2)).isoformat()},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert "error=assign_resource_failed" in resp.headers["location"]

    assert db_session.query(Assignment).filter_by(project_id=project.id, person_id=priya.id).count() == 0


def test_assign_resource_refuses_producer_and_translator(client, db_session):
    project, owner, priya = _seed_project(db_session)

    resp = client.post(f"/projects/{project.id}/assign",
                       data={"person_id": owner.id, "allocation_pct": 30,
                            "start_date": TODAY.isoformat(),
                            "end_date": (TODAY + timedelta(days=2)).isoformat()},
                       follow_redirects=False)
    assert "error=assign_resource_failed" in resp.headers["location"]
    assert db_session.query(Assignment).filter_by(project_id=project.id, person_id=owner.id).count() == 0


def test_assign_resource_refuses_end_before_start(client, db_session):
    project, owner, priya = _seed_project(db_session)

    resp = client.post(f"/projects/{project.id}/assign",
                       data={"person_id": priya.id, "allocation_pct": 30,
                            "start_date": (TODAY + timedelta(days=5)).isoformat(),
                            "end_date": TODAY.isoformat()},
                       follow_redirects=False)
    assert "error=assign_resource_failed" in resp.headers["location"]
    assert db_session.query(Assignment).filter_by(project_id=project.id, person_id=priya.id).count() == 0


def test_project_detail_shows_assign_error_banner(client, db_session):
    project, owner, priya = _seed_project(db_session)
    client.post(f"/projects/{project.id}/assign",
               data={"person_id": owner.id, "allocation_pct": 30,
                    "start_date": TODAY.isoformat(), "end_date": (TODAY + timedelta(days=2)).isoformat()})

    resp = client.get(f"/projects/{project.id}?error=assign_resource_failed")
    assert resp.status_code == 200
    assert "Could not assign" in resp.text
