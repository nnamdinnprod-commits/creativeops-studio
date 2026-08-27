from datetime import date, timedelta

from app.models import PersonRole, Person, Priority, Project, ProjectStatus, ProjectType
from app.seed import seed_phase_templates
from app.services.scheduling import generate_schedule


def test_dashboard_renders_with_no_scheduled_projects(client, db_session):
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Every generated schedule fits its deadline" in resp.text


def test_dashboard_schedule_tile_flags_an_infeasible_project(client, db_session):
    seed_phase_templates(db_session)
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100,
                   skills="", is_external=False)
    db_session.add(owner)
    db_session.commit()
    film = db_session.query(ProjectType).filter_by(name="Film / branded content").one()
    project = Project(name="Tight Turnaround", brand="Hofmann", campaign="C", source_market="ES",
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
