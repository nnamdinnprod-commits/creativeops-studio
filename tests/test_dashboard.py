from datetime import date, timedelta

from app.models import Assignment, PersonRole, Person, Priority, Project, ProjectStatus, ProjectType
from app.seed import seed_assumptions, seed_phase_templates
from app.services.scheduling import generate_schedule


def test_dashboard_renders_with_no_scheduled_projects(client, db_session):
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Every generated schedule fits its deadline" in resp.text


def test_dashboard_schedule_tile_flags_an_infeasible_project(client, db_session):
    seed_phase_templates(db_session)
    seed_assumptions(db_session)
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100,
                   skills="", is_external=False)
    db_session.add(owner)
    db_session.commit()
    film = db_session.query(ProjectType).filter_by(name="Film / branded content").one()
    project = Project(name="Tight Turnaround", brand="Cassenvale", campaign="C", source_market="ES",
                      priority=Priority.high, status=ProjectStatus.brief,
                      deadline=date.today() + timedelta(days=3), owner_id=owner.id, brief_raw="x",
                      project_type_id=film.id)
    db_session.add(project)
    db_session.commit()
    generate_schedule(db_session, project)

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Tight Turnaround" in resp.text
    assert "working day" in resp.text
    assert "Every generated schedule fits its deadline" not in resp.text
    # REVIEW_02.md P5.1: the schedule alert names a project -- it must link to it.
    assert f'href="/projects/{project.id}"' in resp.text


def test_needs_attention_item_links_to_the_project_it_names(client, db_session):
    """REVIEW_02.md P5.1: dashboard attention items are one of the explicitly
    named locations a project must be reachable from."""
    alex = Person(name="Alex", role=PersonRole.senior_designer, capacity_pct=80,
                 skills="layout", is_external=False)
    db_session.add(alex)
    db_session.flush()

    today = date.today()
    p1 = Project(name="Overloaded Project", brand="Fotomera", campaign="C", source_market="NL",
                priority=Priority.high, status=ProjectStatus.in_production,
                deadline=today + timedelta(days=5), owner_id=alex.id, brief_raw="x")
    p2 = Project(name="Other Project", brand="Fotomera", campaign="C", source_market="NL",
                priority=Priority.medium, status=ProjectStatus.assigned,
                deadline=today + timedelta(days=10), owner_id=alex.id, brief_raw="x")
    db_session.add_all([p1, p2])
    db_session.flush()

    db_session.add_all([
        Assignment(person_id=alex.id, project_id=p1.id, allocation_pct=55,
                  start_date=today - timedelta(days=2), end_date=today + timedelta(days=5)),
        Assignment(person_id=alex.id, project_id=p2.id, allocation_pct=40,
                  start_date=today - timedelta(days=1), end_date=today + timedelta(days=10)),
    ])
    db_session.commit()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Needs attention" in resp.text
    named_project_id = p1.id if "Overloaded Project" in resp.text else p2.id
    assert f'href="/projects/{named_project_id}"' in resp.text
