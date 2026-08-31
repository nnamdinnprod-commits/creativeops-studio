from datetime import date, timedelta

from app.models import (
    Assignment,
    Assumption,
    PersonRole,
    PhaseKind,
    Person,
    Priority,
    Project,
    ProjectPhase,
    ProjectStatus,
    ProjectType,
)
from app.seed import seed_assumptions, seed_phase_templates
from app.services.scheduling import generate_schedule
from app.services.assignment import PhaseCandidate
from app.services.timeline import (
    build_timeline,
    conflicted_phase_ids,
    day_position_pct,
    milestone_list,
    week_starts,
)


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
    project = Project(id=1, name="P1", brand="Fotomera", campaign="C", source_market="NL",
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
    project = Project(id=1, name="P1", brand="Fotomera", campaign="C", source_market="NL",
                      priority=Priority.medium, status=ProjectStatus.brief,
                      deadline=date(2026, 9, 18), owner_id=1, brief_raw="x")
    phases = [_phase(1, "Work", date(2026, 9, 7), date(2026, 9, 11))]

    context = build_timeline([(project, phases)], today=date(2027, 1, 1))
    assert context.today_pct is None


def test_milestone_list_includes_only_milestones_sorted_chronologically():
    p1 = Project(id=1, name="P1", brand="Fotomera", campaign="C", source_market="NL",
                priority=Priority.medium, status=ProjectStatus.brief,
                deadline=date(2026, 9, 18), owner_id=1, brief_raw="x")
    p2 = Project(id=2, name="P2", brand="Halveth", campaign="C", source_market="UK",
                priority=Priority.medium, status=ProjectStatus.brief,
                deadline=date(2026, 9, 20), owner_id=1, brief_raw="x")
    phases_p1 = [
        _phase(1, "Work", date(2026, 9, 7), date(2026, 9, 11)),
        _phase(1, "Final approval", date(2026, 9, 16), date(2026, 9, 16),
              kind=PhaseKind.review, is_milestone=True),
    ]
    phases_p2 = [
        _phase(2, "PPM", date(2026, 9, 9), date(2026, 9, 9),
              kind=PhaseKind.review, is_milestone=True),
    ]

    entries = milestone_list([(p1, phases_p1), (p2, phases_p2)], today=date(2026, 9, 10))

    assert [e.phase.name for e in entries] == ["PPM", "Final approval"]
    assert [e.project.name for e in entries] == ["P2", "P1"]
    assert entries[0].is_past is True   # PPM on 9/9, today is 9/10
    assert entries[1].is_past is False  # Final approval on 9/16, today is 9/10


def test_milestone_list_empty_when_no_milestones():
    project = Project(id=1, name="P1", brand="Fotomera", campaign="C", source_market="NL",
                      priority=Priority.medium, status=ProjectStatus.brief,
                      deadline=date(2026, 9, 18), owner_id=1, brief_raw="x")
    phases = [_phase(1, "Work", date(2026, 9, 7), date(2026, 9, 11))]

    assert milestone_list([(project, phases)]) == []


def test_conflicted_phase_ids_flags_only_empty_candidate_lists():
    owner = Person(id=1, name="Dana", role=PersonRole.designer, capacity_pct=100,
                   skills="", is_external=False)
    candidate = PhaseCandidate(person=owner, allocated_pct=0, available_pct=100)

    candidates_by_phase_id = {
        10: [],           # no one available — a conflict
        11: [candidate],  # someone available — not a conflict
    }

    assert conflicted_phase_ids(candidates_by_phase_id) == {10}


def test_conflicted_phase_ids_empty_input_is_empty():
    assert conflicted_phase_ids({}) == set()


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
    seed_assumptions(db_session)
    owner = _seed_person(db_session)
    stills = db_session.query(ProjectType).filter_by(name="Stills").one()
    project = Project(name="Shoot Project", brand="Cassenvale", campaign="C", source_market="ES",
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


def test_route_marks_a_ready_project_as_planned_not_committed(client, db_session):
    """REVIEW_02.md P5.2: 'Ready projects render lighter or outlined to distinguish
    planned from committed work.'"""
    seed_phase_templates(db_session)
    seed_assumptions(db_session)
    owner = _seed_person(db_session)
    stills = db_session.query(ProjectType).filter_by(name="Stills").one()
    ready_project = Project(name="Ready Project", brand="Cassenvale", campaign="C", source_market="ES",
                            priority=Priority.medium, status=ProjectStatus.ready,
                            deadline=date(2026, 12, 1), owner_id=owner.id, brief_raw="x",
                            project_type_id=stills.id)
    committed_project = Project(name="Committed Project", brand="Cassenvale", campaign="C", source_market="ES",
                                priority=Priority.medium, status=ProjectStatus.in_production,
                                deadline=date(2026, 12, 1), owner_id=owner.id, brief_raw="x",
                                project_type_id=stills.id)
    db_session.add_all([ready_project, committed_project])
    db_session.commit()
    generate_schedule(db_session, ready_project)
    generate_schedule(db_session, committed_project)

    resp = client.get("/timeline")
    assert resp.status_code == 200
    assert "Ready Project" in resp.text
    assert "Committed Project" in resp.text
    assert "Planned" in resp.text
    assert resp.text.count("Planned") == 1  # only the Ready-status row gets the badge


def test_route_brand_filter_excludes_non_matching_projects(client, db_session):
    seed_phase_templates(db_session)
    seed_assumptions(db_session)
    owner = _seed_person(db_session)
    stills = db_session.query(ProjectType).filter_by(name="Stills").one()
    project = Project(name="Shoot Project", brand="Cassenvale", campaign="C", source_market="ES",
                      priority=Priority.medium, status=ProjectStatus.brief,
                      deadline=date(2026, 12, 1), owner_id=owner.id, brief_raw="x",
                      project_type_id=stills.id)
    db_session.add(project)
    db_session.commit()
    generate_schedule(db_session, project)

    matching = client.get("/timeline", params={"brand": "Cassenvale"})
    non_matching = client.get("/timeline", params={"brand": "Fotomera"})

    assert "Shoot Project" in matching.text
    assert "Shoot Project" not in non_matching.text
    assert "No scheduled projects match this filter" in non_matching.text


def _seed_project_with_schedule(db_session):
    seed_phase_templates(db_session)
    seed_assumptions(db_session)
    owner = _seed_person(db_session)
    stills = db_session.query(ProjectType).filter_by(name="Stills").one()
    project = Project(name="Shoot Project", brand="Cassenvale", campaign="C", source_market="ES",
                      priority=Priority.medium, status=ProjectStatus.brief,
                      deadline=date(2026, 12, 1), owner_id=owner.id, brief_raw="x",
                      project_type_id=stills.id)
    db_session.add(project)
    db_session.commit()
    generate_schedule(db_session, project)
    retouching = (
        db_session.query(ProjectPhase)
        .filter_by(project_id=project.id, name="Retouching")
        .one()
    )
    return project, retouching


def test_assign_route_assigns_a_role_matched_candidate(client, db_session):
    _project, retouching = _seed_project_with_schedule(db_session)
    designer = Person(name="Dana", role=PersonRole.designer, capacity_pct=100,
                      skills="", is_external=False)
    db_session.add(designer)
    db_session.commit()

    resp = client.post(f"/timeline/phases/{retouching.id}/assign",
                       data={"person_id": designer.id}, follow_redirects=False)
    assert resp.status_code == 303

    db_session.refresh(retouching)
    assert retouching.assigned_person_id == designer.id

    page = client.get("/timeline")
    assert "Dana" in page.text
    assert "Unassign" in page.text


def test_assign_route_rejects_a_role_mismatched_person(client, db_session):
    _project, retouching = _seed_project_with_schedule(db_session)
    translator = Person(name="Jonas", role=PersonRole.translator, capacity_pct=100,
                        skills="", is_external=True)
    db_session.add(translator)
    db_session.commit()

    resp = client.post(f"/timeline/phases/{retouching.id}/assign",
                       data={"person_id": translator.id}, follow_redirects=False)
    assert resp.status_code == 303
    assert "error=assign_failed" in resp.headers["location"]

    db_session.refresh(retouching)
    assert retouching.assigned_person_id is None


def test_unassign_route_clears_the_assignment(client, db_session):
    _project, retouching = _seed_project_with_schedule(db_session)
    designer = Person(name="Dana", role=PersonRole.designer, capacity_pct=100,
                      skills="", is_external=False)
    db_session.add(designer)
    db_session.commit()
    client.post(f"/timeline/phases/{retouching.id}/assign", data={"person_id": designer.id})

    client.post(f"/timeline/phases/{retouching.id}/unassign")

    db_session.refresh(retouching)
    assert retouching.assigned_person_id is None
    assert db_session.query(Assignment).filter_by(project_phase_id=retouching.id).count() == 0


def test_timeline_shows_a_behind_badge_and_ai_panel_for_an_infeasible_schedule(client, db_session):
    seed_phase_templates(db_session)
    seed_assumptions(db_session)
    owner = _seed_person(db_session)
    film = db_session.query(ProjectType).filter_by(name="Film / branded content").one()
    # Film needs ~35 working days; 3 calendar days out is nowhere close, regardless of
    # what "today" actually is when this test runs.
    project = Project(name="Tight Turnaround", brand="Cassenvale", campaign="C", source_market="ES",
                      priority=Priority.high, status=ProjectStatus.brief,
                      deadline=date.today() + timedelta(days=3), owner_id=owner.id, brief_raw="x",
                      project_type_id=film.id)
    db_session.add(project)
    db_session.commit()
    generate_schedule(db_session, project)

    resp = client.get("/timeline")
    assert resp.status_code == 200
    assert "Behind" in resp.text
    assert "Schedule feasibility" in resp.text
    assert "working day" in resp.text


def test_timeline_does_not_show_behind_badge_for_a_feasible_schedule(client, db_session):
    seed_phase_templates(db_session)
    seed_assumptions(db_session)
    owner = _seed_person(db_session)
    social = db_session.query(ProjectType).filter_by(name="Social / AI-generated content").one()
    project = Project(name="Plenty of Runway", brand="Cassenvale", campaign="C", source_market="ES",
                      priority=Priority.medium, status=ProjectStatus.brief,
                      deadline=date.today() + timedelta(days=90), owner_id=owner.id, brief_raw="x",
                      project_type_id=social.id)
    db_session.add(project)
    db_session.commit()
    generate_schedule(db_session, project)

    resp = client.get("/timeline")
    assert resp.status_code == 200
    assert "Behind" not in resp.text


def test_timeline_outlines_a_phase_with_no_available_candidate(client, db_session):
    _project, _retouching = _seed_project_with_schedule(db_session)
    # No designer exists in the roster at all — Retouching (requires "designer") has
    # zero candidates by construction.
    resp = client.get("/timeline")
    assert resp.status_code == 200
    assert "ring-2 ring-red-600" in resp.text
    assert "no one with capacity for this role" in resp.text.lower()


def test_timeline_does_not_outline_a_phase_once_a_candidate_exists(client, db_session):
    _project, retouching = _seed_project_with_schedule(db_session)
    # Stills also has a Shoot phase requiring senior_designer, which stays unfilled here —
    # only Retouching (designer) should stop being flagged, so compare counts, not absence.
    before = client.get("/timeline").text.count("ring-2 ring-red-600")

    designer = Person(name="Dana", role=PersonRole.designer, capacity_pct=100,
                      skills="", is_external=False)
    db_session.add(designer)
    db_session.commit()

    after = client.get("/timeline").text.count("ring-2 ring-red-600")
    assert after == before - 1


def test_timeline_stops_computing_candidates_for_a_phase_once_assigned(client, db_session):
    """An assigned phase is dropped from candidates_by_phase_id entirely (app/routes/
    timeline.py only computes candidates for phase.assigned_person_id is None), so it can
    never be outlined as a conflict regardless of who else could theoretically take it on."""
    _project, retouching = _seed_project_with_schedule(db_session)
    designer = Person(name="Dana", role=PersonRole.designer, capacity_pct=100,
                      skills="", is_external=False)
    db_session.add(designer)
    db_session.commit()
    client.post(f"/timeline/phases/{retouching.id}/assign", data={"person_id": designer.id})

    resp = client.get("/timeline")
    assert resp.status_code == 200
    # Shoot (senior_designer) is still unfilled and still flagged — only Retouching, now
    # assigned, is excluded from the check.
    assert resp.text.count("ring-2 ring-red-600") == 1


def test_timeline_feasibility_panel_reflects_a_live_edited_assumption(client, db_session):
    """DECISIONS.md 027: editing client_review_minimum_days on /assumptions changes the
    compress_review option shown for an infeasible schedule, no code change required."""
    seed_phase_templates(db_session)
    seed_assumptions(db_session)
    owner = _seed_person(db_session)
    film = db_session.query(ProjectType).filter_by(name="Film / branded content").one()
    project = Project(name="Tight Turnaround", brand="Cassenvale", campaign="C", source_market="ES",
                      priority=Priority.high, status=ProjectStatus.brief,
                      deadline=date.today() + timedelta(days=3), owner_id=owner.id, brief_raw="x",
                      project_type_id=film.id)
    db_session.add(project)
    db_session.commit()
    generate_schedule(db_session, project)

    minimum = db_session.query(Assumption).filter_by(key="client_review_minimum_days").one()
    minimum.value_numeric = 1
    db_session.commit()

    resp = client.get("/timeline")
    assert resp.status_code == 200
    assert "days to 1" in resp.text  # the compressed-to value, not the hardcoded default of 2
