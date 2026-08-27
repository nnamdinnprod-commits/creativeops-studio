from datetime import date

from app.models import (
    PersonRole,
    PhaseKind,
    Person,
    Priority,
    Project,
    ProjectPhase,
    ProjectStatus,
    ProjectType,
)
from app.seed import seed_phase_templates
from app.services.scheduling import generate_schedule
from app.services.timeline import build_timeline, day_position_pct, week_starts


def _phase(project_id, name, start, end, kind=PhaseKind.production, is_milestone=False):
    return ProjectPhase(
        project_id=project_id, name=name, kind=kind, start_date=start, end_date=end,
        is_milestone=is_milestone, is_anchored=False,
    )


def test_week_starts_spans_full_weeks():
    # 2026-09-09 is a Wednesday, 2026-09-11 is a Friday.
    starts = week_starts(date(2026, 9, 9), date(2026, 9, 11))
    assert starts == [date(2026, 9, 7)]  # the Monday of that one week

    starts = week_starts(date(2026, 9, 7), date(2026, 9, 15))  # Monday through the next Tuesday
    assert starts == [date(2026, 9, 7), date(2026, 9, 14)]


def test_day_position_pct():
    assert day_position_pct(date(2026, 9, 7), date(2026, 9, 7), 10) == 0.0
    assert day_position_pct(date(2026, 9, 12), date(2026, 9, 7), 10) == 50.0


def test_build_timeline_empty_when_no_phases():
    context = build_timeline([], today=date(2026, 9, 9))
    assert context.rows == []
    assert context.today_pct is None


def test_build_timeline_positions_bars_and_today_line():
    project = Project(id=1, name="P1", brand="Albelli", campaign="C", source_market="NL",
                      priority=Priority.medium, status=ProjectStatus.brief,
                      deadline=date(2026, 9, 18), owner_id=1, brief_raw="x")
    phases = [
        _phase(1, "Work", date(2026, 9, 7), date(2026, 9, 11)),
        _phase(1, "Sign-off", date(2026, 9, 14), date(2026, 9, 14), is_milestone=True),
    ]

    context = build_timeline([(project, phases)], today=date(2026, 9, 9))

    # Range extends to full week boundaries around the phases (Mon 9/7 .. Sun 9/20 covers the
    # 9/14 Monday-anchored week).
    assert context.range_start == date(2026, 9, 7)
    assert len(context.rows) == 1
    row = context.rows[0]
    assert row.project.id == 1
    assert len(row.bars) == 2
    assert row.bars[0].phase.name == "Work"
    assert row.bars[0].left_pct == 0.0
    assert row.bars[1].phase.name == "Sign-off"
    assert row.bars[1].width_pct > 0  # milestone still gets a visible, non-zero width
    assert context.today_pct is not None
    assert 0 < context.today_pct < 100


def test_build_timeline_today_outside_range_is_none():
    project = Project(id=1, name="P1", brand="Albelli", campaign="C", source_market="NL",
                      priority=Priority.medium, status=ProjectStatus.brief,
                      deadline=date(2026, 9, 18), owner_id=1, brief_raw="x")
    phases = [_phase(1, "Work", date(2026, 9, 7), date(2026, 9, 11))]

    context = build_timeline([(project, phases)], today=date(2027, 1, 1))
    assert context.today_pct is None


def _seed_person(db_session):
    person = Person(name="Owner", role=PersonRole.producer, capacity_pct=100,
                    skills="", is_external=False)
    db_session.add(person)
    db_session.commit()
    return person


def test_route_renders_empty_state_with_no_schedules(client, db_session):
    resp = client.get("/timeline")
    assert resp.status_code == 200
    assert "No projects have a generated schedule yet" in resp.text


def test_route_renders_a_generated_schedule(client, db_session):
    seed_phase_templates(db_session)
    owner = _seed_person(db_session)
    stills = db_session.query(ProjectType).filter_by(name="Stills").one()
    project = Project(name="Shoot Project", brand="Hofmann", campaign="C", source_market="ES",
                      priority=Priority.medium, status=ProjectStatus.brief,
                      deadline=date(2026, 12, 1), owner_id=owner.id, brief_raw="x",
                      project_type_id=stills.id)
    db_session.add(project)
    db_session.commit()
    generate_schedule(db_session, project)

    resp = client.get("/timeline")
    assert resp.status_code == 200
    assert "Shoot Project" in resp.text
    assert "Brief &amp; scoping" in resp.text or "Brief & scoping" in resp.text


def test_route_brand_filter_excludes_non_matching_projects(client, db_session):
    seed_phase_templates(db_session)
    owner = _seed_person(db_session)
    stills = db_session.query(ProjectType).filter_by(name="Stills").one()
    project = Project(name="Shoot Project", brand="Hofmann", campaign="C", source_market="ES",
                      priority=Priority.medium, status=ProjectStatus.brief,
                      deadline=date(2026, 12, 1), owner_id=owner.id, brief_raw="x",
                      project_type_id=stills.id)
    db_session.add(project)
    db_session.commit()
    generate_schedule(db_session, project)

    matching = client.get("/timeline", params={"brand": "Hofmann"})
    non_matching = client.get("/timeline", params={"brand": "Albelli"})

    assert "Shoot Project" in matching.text
    assert "Shoot Project" not in non_matching.text
    assert "No scheduled projects match this filter" in non_matching.text
