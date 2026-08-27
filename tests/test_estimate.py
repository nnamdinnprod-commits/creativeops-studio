from datetime import date

import pytest

from app.models import Assumption
from app.seed import seed_assumptions, seed_phase_templates
from app.services.estimate import compute_estimate, volume_factor_for


def _seed(db_session):
    seed_phase_templates(db_session)
    seed_assumptions(db_session)


def test_volume_factor_for_reads_live_assumption_values(db_session):
    _seed(db_session)
    assert volume_factor_for(db_session, 6) == 1.0
    assert volume_factor_for(db_session, 15) == 1.6
    assert volume_factor_for(db_session, 30) == 2.5
    assert volume_factor_for(db_session, 60) == 3.8

    band = db_session.query(Assumption).filter_by(key="volume_scale_1_6").one()
    band.value_numeric = 1.25
    db_session.commit()

    assert volume_factor_for(db_session, 6) == 1.25  # proves this reads live, not a constant


def test_volume_factor_for_out_of_range_raises(db_session):
    _seed(db_session)
    with pytest.raises(ValueError):
        volume_factor_for(db_session, 0)
    with pytest.raises(ValueError):
        volume_factor_for(db_session, 61)


def test_compute_estimate_basic_social(db_session):
    _seed(db_session)
    result = compute_estimate(
        db_session, work_type="social", asset_count=6, original_photography=False,
        review_rounds=2, target_market_count=0, localisation_required=False,
        confidence="medium", today=date(2026, 9, 7),
    )

    assert 0 < result.duration_low_days <= result.duration_high_days
    assert 0 < result.cost_low <= result.cost_high
    assert result.currency == "EUR"
    assert result.earliest_delivery >= date(2026, 9, 7)
    assert result.lines


def test_compute_estimate_unknown_work_type_raises(db_session):
    _seed(db_session)
    with pytest.raises(ValueError):
        compute_estimate(db_session, work_type="not_a_type", asset_count=6,
                         original_photography=False, review_rounds=2,
                         target_market_count=0, localisation_required=False,
                         confidence="medium")


def test_compute_estimate_unknown_confidence_raises(db_session):
    _seed(db_session)
    with pytest.raises(ValueError):
        compute_estimate(db_session, work_type="social", asset_count=6,
                         original_photography=False, review_rounds=2,
                         target_market_count=0, localisation_required=False,
                         confidence="extreme")


def test_original_photography_adds_duration_and_cost(db_session):
    _seed(db_session)
    kwargs = dict(work_type="social", asset_count=6, review_rounds=2,
                 target_market_count=0, localisation_required=False, confidence="medium")

    without = compute_estimate(db_session, original_photography=False, **kwargs)
    with_photo = compute_estimate(db_session, original_photography=True, **kwargs)

    assert with_photo.duration_high_days > without.duration_high_days
    assert with_photo.cost_high > without.cost_high


def test_localisation_adds_cost_only_when_markets_present(db_session):
    _seed(db_session)
    kwargs = dict(work_type="social", asset_count=6, original_photography=False,
                 review_rounds=2, confidence="medium")

    no_markets = compute_estimate(db_session, target_market_count=0,
                                  localisation_required=False, **kwargs)
    with_markets = compute_estimate(db_session, target_market_count=2,
                                    localisation_required=True, **kwargs)

    assert with_markets.duration_high_days > no_markets.duration_high_days
    assert with_markets.cost_high > no_markets.cost_high


def test_more_review_rounds_increases_duration(db_session):
    _seed(db_session)
    kwargs = dict(work_type="social", asset_count=6, original_photography=False,
                 target_market_count=0, localisation_required=False, confidence="medium")

    fewer = compute_estimate(db_session, review_rounds=1, **kwargs)
    more = compute_estimate(db_session, review_rounds=4, **kwargs)

    assert more.duration_high_days > fewer.duration_high_days


def test_lower_confidence_widens_the_range(db_session):
    _seed(db_session)
    kwargs = dict(work_type="social", asset_count=6, original_photography=False,
                 review_rounds=2, target_market_count=0, localisation_required=False)

    high_conf = compute_estimate(db_session, confidence="high", **kwargs)
    low_conf = compute_estimate(db_session, confidence="low", **kwargs)

    high_width = high_conf.duration_high_days - high_conf.duration_low_days
    low_width = low_conf.duration_high_days - low_conf.duration_low_days
    assert low_width > high_width


def test_editing_client_review_days_changes_the_estimate(db_session):
    """The core promise: editing an Assumption value recomputes live, no code change."""
    _seed(db_session)
    kwargs = dict(work_type="social", asset_count=6, original_photography=False,
                 review_rounds=2, target_market_count=0, localisation_required=False,
                 confidence="medium")

    before = compute_estimate(db_session, **kwargs)

    review_days = db_session.query(Assumption).filter_by(key="client_review_days").one()
    review_days.value_numeric = 10
    db_session.commit()

    after = compute_estimate(db_session, **kwargs)
    assert after.duration_high_days > before.duration_high_days


def test_editing_a_rate_band_changes_the_cost_only(db_session):
    from app.models import PersonRole, RateBand

    _seed(db_session)
    kwargs = dict(work_type="social", asset_count=6, original_photography=False,
                 review_rounds=2, target_market_count=0, localisation_required=False,
                 confidence="medium")
    before = compute_estimate(db_session, **kwargs)

    band = db_session.query(RateBand).filter_by(role=PersonRole.producer).one()
    band.low += 1000
    band.high += 1000
    db_session.commit()

    after = compute_estimate(db_session, **kwargs)
    assert after.cost_low > before.cost_low
    assert after.duration_low_days == before.duration_low_days  # rates don't move duration


@pytest.mark.parametrize("work_type", ["film", "event", "stills", "social"])
def test_asset_count_affects_duration_for_every_work_type(db_session, work_type):
    """Regression: only Film's PhaseTemplate rows carry scales_with_volume=True
    (DECISIONS.md 016) — compute_estimate() must not silently ignore asset_count for the
    other three work types, including the docs' own primary example (social)."""
    _seed(db_session)
    kwargs = dict(work_type=work_type, original_photography=False, review_rounds=2,
                 target_market_count=0, localisation_required=False, confidence="medium")

    few = compute_estimate(db_session, asset_count=6, **kwargs)
    many = compute_estimate(db_session, asset_count=30, **kwargs)

    assert many.duration_high_days > few.duration_high_days
    assert many.cost_high > few.cost_high
