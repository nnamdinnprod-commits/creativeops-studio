from datetime import date

import pytest

from app.models import (
    Assumption,
    PersonRole,
    PhaseKind,
    PhaseTemplate,
    Person,
    Priority,
    Project,
    ProjectPhase,
    ProjectStatus,
    ProjectType,
)
from app.seed import seed_assumptions, seed_phase_templates
from app.services.scheduling import (
    CLIENT_REVIEW_DAYS,
    CLIENT_REVIEW_MINIMUM_DAYS,
    back_schedule,
    build_feasibility_facts,
    generate_schedule,
    volume_factor_for,
)


def _template(sequence, name, days, kind=PhaseKind.production, is_milestone=False,
              is_client_review=False, scales_with_volume=False):
    return PhaseTemplate(
        project_type_id=1, sequence=sequence, name=name, default_days=days, kind=kind,
        required_roles="producer", is_milestone=is_milestone,
        is_client_review=is_client_review, scales_with_volume=scales_with_volume,
    )


def test_volume_factor_bands():
    assert volume_factor_for(1) == 1.0
    assert volume_factor_for(6) == 1.0
    assert volume_factor_for(7) == 1.6
    assert volume_factor_for(15) == 1.6
    assert volume_factor_for(16) == 2.5
    assert volume_factor_for(30) == 2.5
    assert volume_factor_for(31) == 3.8
    assert volume_factor_for(60) == 3.8


def test_volume_factor_out_of_range_raises():
    with pytest.raises(ValueError):
        volume_factor_for(0)
    with pytest.raises(ValueError):
        volume_factor_for(61)


def test_production_phase_then_milestone_at_delivery():
    templates = [
        _template(1, "Work", 2),
        _template(2, "Sign-off", 0, kind=PhaseKind.review, is_milestone=True, is_client_review=True),
    ]
    result = back_schedule(templates, delivery_date=date(2026, 9, 4))  # Friday

    milestone, work = result.phases[1], result.phases[0]
    assert milestone.start_date == milestone.end_date == date(2026, 9, 4)
    assert work.start_date == date(2026, 9, 2) and work.end_date == date(2026, 9, 3)
    assert result.project_start == date(2026, 9, 2)


def test_working_days_skip_weekends():
    templates = [_template(1, "Work", 3)]
    result = back_schedule(templates, delivery_date=date(2026, 9, 7))  # Monday

    phase = result.phases[0]
    assert phase.end_date == date(2026, 9, 7)
    assert phase.start_date == date(2026, 9, 3)  # Thursday — spans the weekend
    for d in (phase.start_date, phase.end_date):
        assert d.weekday() < 5


def test_client_review_duration_overrides_template_default():
    # A 2-day template value for a non-milestone review phase — PLANNING.md point 6 says
    # review windows come from ASSUMPTIONS.md, not the template.
    templates = [_template(1, "Client review", 2, kind=PhaseKind.review, is_client_review=True)]
    result = back_schedule(templates, delivery_date=date(2026, 9, 10))

    assert result.phases[0].working_days == CLIENT_REVIEW_DAYS
    assert result.phases[0].working_days != 2


def test_scales_with_volume_multiplies_duration():
    templates = [_template(1, "Shoot", 2, scales_with_volume=True)]
    result = back_schedule(templates, delivery_date=date(2026, 9, 10), volume_factor=2.5)

    assert result.phases[0].working_days == 5  # round(2 * 2.5)


def test_past_start_is_flagged_not_compressed():
    templates = [_template(1, "Work", 5)]
    naive = back_schedule(templates, delivery_date=date(2026, 1, 9), today=date(2026, 1, 1))
    flagged = back_schedule(templates, delivery_date=date(2026, 1, 9), today=date(2026, 8, 27))

    assert naive.is_feasible is True
    assert flagged.is_feasible is False
    assert flagged.shortfall_working_days > 0
    # Same computed dates either way — the shortfall is reported, not compressed away.
    assert flagged.phases[0].start_date == naive.phases[0].start_date
    assert flagged.phases[0].end_date == naive.phases[0].end_date


def test_full_film_template_is_internally_consistent(db_session):
    seed_phase_templates(db_session)
    film = db_session.query(ProjectType).filter_by(name="Film / branded content").one()
    templates = (
        db_session.query(PhaseTemplate)
        .filter_by(project_type_id=film.id)
        .order_by(PhaseTemplate.sequence)
        .all()
    )

    result = back_schedule(templates, delivery_date=date(2026, 12, 4))

    assert len(result.phases) == len(templates)
    assert [p.sequence for p in result.phases] == [t.sequence for t in templates]
    assert result.phases[-1].end_date == date(2026, 12, 4)
    assert result.phases[0].start_date == result.project_start

    for earlier, later in zip(result.phases, result.phases[1:]):
        gap = (later.start_date - earlier.end_date).days
        assert gap >= 1  # never overlapping
        assert earlier.end_date.weekday() < 5
        assert later.start_date.weekday() < 5


def _seed_project(db_session, project_type_id=None, deadline=date(2026, 12, 4), volume_factor=1.0):
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100,
                   skills="", is_external=False)
    db_session.add(owner)
    db_session.flush()

    project = Project(name="P1", brand="Albelli", campaign="C", source_market="NL",
                      priority=Priority.medium, status=ProjectStatus.brief, deadline=deadline,
                      owner_id=owner.id, brief_raw="x", project_type_id=project_type_id,
                      volume_factor=volume_factor)
    db_session.add(project)
    db_session.commit()
    return project


def test_generate_schedule_persists_project_phases_matching_back_schedule(db_session):
    seed_phase_templates(db_session)
    seed_assumptions(db_session)
    stills = db_session.query(ProjectType).filter_by(name="Stills").one()
    project = _seed_project(db_session, project_type_id=stills.id, deadline=date(2026, 10, 30))

    phases = generate_schedule(db_session, project)

    templates = (
        db_session.query(PhaseTemplate)
        .filter_by(project_type_id=stills.id)
        .order_by(PhaseTemplate.sequence)
        .all()
    )
    expected = back_schedule(templates, delivery_date=date(2026, 10, 30))

    assert len(phases) == len(expected.phases)
    for stored, computed in zip(phases, expected.phases):
        assert stored.name == computed.name
        assert stored.start_date == computed.start_date
        assert stored.end_date == computed.end_date
        assert stored.is_milestone == computed.is_milestone
        assert stored.project_id == project.id
        assert stored.status.value == "not_started"
        assert stored.assigned_person_id is None
        assert stored.is_anchored is False


def test_generate_schedule_without_project_type_raises(db_session):
    project = _seed_project(db_session, project_type_id=None)

    with pytest.raises(ValueError):
        generate_schedule(db_session, project)


def test_regenerating_a_schedule_replaces_rather_than_duplicates(db_session):
    seed_phase_templates(db_session)
    seed_assumptions(db_session)
    stills = db_session.query(ProjectType).filter_by(name="Stills").one()
    project = _seed_project(db_session, project_type_id=stills.id, deadline=date(2026, 10, 30))

    first = generate_schedule(db_session, project)
    project.deadline = date(2026, 11, 13)
    db_session.commit()
    second = generate_schedule(db_session, project)

    stored = db_session.query(ProjectPhase).filter_by(project_id=project.id).all()
    assert len(stored) == len(first) == len(second)
    assert second[-1].end_date == date(2026, 11, 13)
    # The stale first-schedule dates are actually gone, not just outnumbered by coincidence.
    assert not any(p.end_date == date(2026, 10, 30) for p in stored)


def _project_phase(name, start, end, kind=PhaseKind.production, is_milestone=False):
    return ProjectPhase(
        project_id=1, name=name, kind=kind, start_date=start, end_date=end,
        is_milestone=is_milestone, is_anchored=False,
    )


def test_build_feasibility_facts_feasible_when_start_not_in_past():
    phases = [_project_phase("Work", date(2026, 9, 10), date(2026, 9, 14))]
    facts = build_feasibility_facts(phases, deadline=date(2026, 9, 14), today=date(2026, 9, 3))
    assert facts == {"feasible": True}


def test_build_feasibility_facts_empty_phases_is_feasible():
    assert build_feasibility_facts([], deadline=date(2026, 9, 14)) == {"feasible": True}


def test_build_feasibility_facts_computes_shortfall_and_candidates():
    phases = [
        _project_phase("Concept", date(2026, 9, 3), date(2026, 9, 3), kind=PhaseKind.prep),
        _project_phase("Client review", date(2026, 9, 4), date(2026, 9, 9), kind=PhaseKind.review),
        _project_phase("Revisions", date(2026, 9, 10), date(2026, 9, 11), kind=PhaseKind.production),
        _project_phase("Delivery", date(2026, 9, 14), date(2026, 9, 14), kind=PhaseKind.delivery),
    ]
    facts = build_feasibility_facts(phases, deadline=date(2026, 9, 14), today=date(2026, 9, 10))

    assert facts["feasible"] is False
    assert facts["shortfall_days"] == 5  # working days from 9/3 (Thu) to 9/10 (Thu)
    assert facts["project_start"] == "2026-09-03"

    candidates = facts["binding_constraint_candidates"]
    assert len(candidates) <= 3
    assert candidates[0] == {"phase_name": "Client review", "working_days": 4}

    options = {opt["action"]: opt for opt in facts["options"]}
    assert options["compress_review"] == {
        "action": "compress_review", "detail": "Client review 4 days to 2", "recovers_days": 2,
    }
    assert options["drop_revisions"] == {
        "action": "drop_revisions", "detail": "drop Revisions (2 days)", "recovers_days": 2,
    }
    assert options["move_delivery"] == {
        "action": "move_delivery", "detail": "to 2026-09-21", "recovers_days": 5,
    }


def test_build_feasibility_facts_no_compress_review_option_at_or_below_minimum():
    phases = [
        _project_phase("Client review", date(2026, 9, 3), date(2026, 9, 4), kind=PhaseKind.review),
    ]
    facts = build_feasibility_facts(phases, deadline=date(2026, 9, 4), today=date(2026, 9, 10))
    actions = {opt["action"] for opt in facts["options"]}
    assert "compress_review" not in actions


def test_build_feasibility_facts_excludes_milestones_from_candidates_and_options():
    phases = [
        _project_phase("PPM", date(2026, 9, 3), date(2026, 9, 3), kind=PhaseKind.review, is_milestone=True),
        _project_phase("Work", date(2026, 9, 3), date(2026, 9, 3), kind=PhaseKind.production),
    ]
    facts = build_feasibility_facts(phases, deadline=date(2026, 9, 3), today=date(2026, 9, 10))
    names = {c["phase_name"] for c in facts["binding_constraint_candidates"]}
    assert "PPM" not in names


def test_generate_schedule_reads_client_review_days_live(db_session):
    """The core promise: editing /assumptions and regenerating a schedule changes the
    persisted ProjectPhase durations, no code change required (DECISIONS.md 027)."""
    seed_phase_templates(db_session)
    seed_assumptions(db_session)
    stills = db_session.query(ProjectType).filter_by(name="Stills").one()
    project = _seed_project(db_session, project_type_id=stills.id, deadline=date(2026, 10, 30))

    baseline = generate_schedule(db_session, project)
    baseline_review = next(p for p in baseline if p.name == "Client review")
    baseline_days = (baseline_review.end_date - baseline_review.start_date).days + 1

    review_assumption = db_session.query(Assumption).filter_by(key="client_review_days").one()
    review_assumption.value_numeric = 10
    db_session.commit()

    updated = generate_schedule(db_session, project)
    updated_review = next(p for p in updated if p.name == "Client review")
    updated_days = (updated_review.end_date - updated_review.start_date).days + 1

    assert updated_days > baseline_days


def test_generate_schedule_without_assumptions_seeded_raises(db_session):
    """Documents the hard dependency this introduces — see the ordering fix in
    app/seed.py's main() (Assumptions must seed before demo schedules)."""
    seed_phase_templates(db_session)
    stills = db_session.query(ProjectType).filter_by(name="Stills").one()
    project = _seed_project(db_session, project_type_id=stills.id, deadline=date(2026, 10, 30))

    with pytest.raises(ValueError, match="client_review_days"):
        generate_schedule(db_session, project)
