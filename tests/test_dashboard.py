import json
import re
from datetime import date, timedelta

from app.models import (
    Assignment,
    BriefAnalysis,
    PersonRole,
    Person,
    Priority,
    Project,
    ProjectStatus,
    ProjectType,
)
from app.seed import seed_assumptions, seed_phase_templates
from app.services.scheduling import generate_schedule


def _tile_count(html: str, label: str) -> int:
    match = re.search(rf"{label}</div>\s*<div[^>]*>(\d+)</div>", html)
    assert match is not None, f"could not find the {label!r} tile in the dashboard HTML"
    return int(match.group(1))


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


def test_low_readiness_brief_counts_as_at_risk_not_on_track(client, db_session):
    """REVIEW_03.md R1 audit: dashboard.py's at-risk filter used to only count
    the capacity/localisation/deadline attention causes, silently dropping
    "brief" — a project flagged in the Needs Attention panel for a low
    readiness score counted toward neither At risk nor Blocked (no
    estimated_days here, so it can't be brief-stalled either) and was
    silently bucketed as on-track, contradicting the panel above it."""
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100,
                   skills="", is_external=False)
    db_session.add(owner)
    db_session.flush()

    project = Project(name="Vague Brief Project", brand="Fotomera", campaign="C",
                      source_market="NL", priority=Priority.medium, status=ProjectStatus.brief,
                      deadline=date.today() + timedelta(days=21), owner_id=owner.id,
                      brief_raw="x")
    db_session.add(project)
    db_session.flush()

    analysis = BriefAnalysis(raw_text="x", extracted_json="{}", readiness_score=50,
                             missing_fields_json=json.dumps(["deadline"]),
                             blocking_reasons=json.dumps({}), created_project_id=project.id)
    db_session.add(analysis)
    db_session.commit()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Vague Brief Project" in resp.text  # named in the Needs Attention panel
    assert _tile_count(resp.text, "At risk") == 1
    assert _tile_count(resp.text, "On track") == 0
    assert _tile_count(resp.text, "Blocked") == 0


def test_on_track_at_risk_and_blocked_partition_active_projects(client, db_session):
    """REVIEW_03.md item (b): these three tiles disagreed with each other for
    two review rounds (a project could count in none of them, or the wrong
    one). Lock the invariant down against the full seed data so it can't
    silently drift again: every active project lands in exactly one tile."""
    from app.seed import (
        backfill_project_types,
        seed,
        seed_assumptions,
        seed_demo_schedules,
        seed_phase_templates,
    )

    seed(db_session)
    seed_phase_templates(db_session)
    seed_assumptions(db_session)
    seed_demo_schedules(db_session)
    backfill_project_types(db_session)

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    active = _tile_count(resp.text, "Active projects")
    on_track = _tile_count(resp.text, "On track")
    at_risk = _tile_count(resp.text, "At risk")
    blocked = _tile_count(resp.text, "Blocked")
    assert on_track + at_risk + blocked == active
    assert active > 0  # a vacuously-true 0 == 0 would defeat the point of this test


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
