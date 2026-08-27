import pytest

from app.models import Assumption, PersonRole, RateBand
from app.seed import ASSUMPTIONS, RATE_BANDS, seed_assumptions
from app.services.assumptions import get_rate_band, get_value, reset_all


def test_seed_creates_expected_row_counts(db_session):
    seed_assumptions(db_session)
    assert db_session.query(Assumption).count() == len(ASSUMPTIONS) == 21
    assert db_session.query(RateBand).count() == len(RATE_BANDS) == 6


def test_seed_assumption_keys_are_unique(db_session):
    seed_assumptions(db_session)
    keys = [a.key for a in db_session.query(Assumption).all()]
    assert len(keys) == len(set(keys))


def test_seed_categories_match_assumptions_md(db_session):
    seed_assumptions(db_session)
    categories = {a.category for a in db_session.query(Assumption).all()}
    assert categories == {
        "Review and approval cycles", "Lead times", "Volume scaling", "Confidence bands",
    }


def test_seed_every_rate_band_role_covered(db_session):
    seed_assumptions(db_session)
    roles = {rb.role for rb in db_session.query(RateBand).all()}
    assert roles == {
        PersonRole.producer, PersonRole.senior_designer, PersonRole.designer,
        PersonRole.motion_designer, PersonRole.copywriter, PersonRole.translator,
    }


def test_get_value_returns_the_live_value(db_session):
    seed_assumptions(db_session)
    assert get_value(db_session, "client_review_days") == 3


def test_get_value_raises_for_unknown_key(db_session):
    seed_assumptions(db_session)
    with pytest.raises(ValueError):
        get_value(db_session, "not_a_real_key")


def test_get_rate_band_returns_correct_role(db_session):
    seed_assumptions(db_session)
    band = get_rate_band(db_session, PersonRole.senior_designer)
    assert band is not None
    assert band.low == 500 and band.high == 700


def test_reset_all_restores_default_after_edit(db_session):
    seed_assumptions(db_session)
    assumption = db_session.query(Assumption).filter_by(key="client_review_days").one()
    assumption.value_numeric = 99
    db_session.commit()
    assert get_value(db_session, "client_review_days") == 99

    reset_all(db_session)
    assert get_value(db_session, "client_review_days") == 3


def test_reset_all_does_not_touch_rate_bands(db_session):
    seed_assumptions(db_session)
    band = db_session.query(RateBand).filter_by(role=PersonRole.designer).one()
    band.low = 999
    db_session.commit()

    reset_all(db_session)

    db_session.refresh(band)
    assert band.low == 999


def test_route_renders_grouped_table(client, db_session):
    seed_assumptions(db_session)
    resp = client.get("/assumptions")
    assert resp.status_code == 200
    assert "Review and approval cycles" in resp.text
    assert "client_review_days" in resp.text
    assert "Day rate bands" in resp.text
    assert "Producer" in resp.text


def test_route_update_assumption_persists_new_value(client, db_session):
    seed_assumptions(db_session)
    assumption = db_session.query(Assumption).filter_by(key="client_review_days").one()

    resp = client.post(f"/assumptions/{assumption.id}/update",
                       data={"value_numeric": "5"}, follow_redirects=False)
    assert resp.status_code == 303

    db_session.refresh(assumption)
    assert assumption.value_numeric == 5


def test_route_reset_restores_defaults(client, db_session):
    seed_assumptions(db_session)
    assumption = db_session.query(Assumption).filter_by(key="client_review_days").one()
    client.post(f"/assumptions/{assumption.id}/update", data={"value_numeric": "99"})

    resp = client.post("/assumptions/reset", follow_redirects=False)
    assert resp.status_code == 303

    db_session.refresh(assumption)
    assert assumption.value_numeric == 3


def test_route_update_rate_band_persists(client, db_session):
    seed_assumptions(db_session)
    band = db_session.query(RateBand).filter_by(role=PersonRole.designer).one()

    resp = client.post(f"/assumptions/rate-bands/{band.id}/update",
                       data={"low": "400", "high": "600"}, follow_redirects=False)
    assert resp.status_code == 303

    db_session.refresh(band)
    assert band.low == 400 and band.high == 600
