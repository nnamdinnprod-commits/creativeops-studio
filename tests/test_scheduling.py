from datetime import date

import pytest

from app.models import PhaseKind, PhaseTemplate, ProjectType
from app.seed import seed_phase_templates
from app.services.scheduling import (
    CLIENT_REVIEW_DAYS,
    back_schedule,
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
