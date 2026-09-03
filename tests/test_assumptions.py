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
    assert "Day rate bands" in resp.text
    assert "Producer" in resp.text


def test_route_hides_raw_keys_behind_human_labels(client, db_session):
    """REVIEW_03.md R9.1: the raw database key must never be shown -- a human
    label instead, with the fuller description underneath it."""
    seed_assumptions(db_session)
    resp = client.get("/assumptions")
    assert resp.status_code == 200
    assert "client_review_days" not in resp.text
    assert "volume_scale_16_30" not in resp.text
    assert "confidence_high_low_factor" not in resp.text
    assert "Client review round" in resp.text
    assert "Length of a standard client review round" in resp.text


def test_route_collapses_confidence_bands_to_four_ranges(client, db_session):
    """REVIEW_03.md R9.2: eight rows (four tiers x low/high factor) become
    four, each expressed as the range a producer actually reads."""
    seed_assumptions(db_session)
    resp = client.get("/assumptions")
    assert resp.status_code == 200
    for label in ["Fully specified", "Mostly specified", "Partly assumed", "Mostly assumed"]:
        assert label in resp.text
    assert "-5% / +10%" in resp.text or "−5% / +10%" in resp.text


def test_route_states_the_reason_for_volume_scaling(client, db_session):
    """REVIEW_03.md R9.3."""
    seed_assumptions(db_session)
    resp = client.get("/assumptions")
    assert resp.status_code == 200
    assert "effort grows more slowly than asset count" in resp.text.lower()


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


def test_route_update_client_review_days_reschedules_every_scheduled_project(client, db_session):
    """REVIEW_02.md P3: 'Change an assumption -> reschedule every affected project.'
    client_review_days is the one Assumption generate_schedule() reads once and
    persists as ProjectPhase rows — everything else here (volume scaling, lead
    times, confidence bands, client_review_minimum_days) is already read live at
    display time, so there's nothing stored for those to leave stale."""
    from datetime import date
    from app.models import Priority, Project, ProjectPhase, ProjectStatus, ProjectType, Person, PersonRole
    from app.seed import seed_phase_templates
    from app.services.scheduling import generate_schedule

    seed_assumptions(db_session)
    seed_phase_templates(db_session)
    stills = db_session.query(ProjectType).filter_by(name="Stills").one()
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    db_session.add(owner)
    db_session.flush()
    project = Project(name="P1", brand="Fotomera", campaign="C", source_market="NL",
                      priority=Priority.medium, status=ProjectStatus.ready,
                      deadline=date(2026, 10, 30), owner_id=owner.id, brief_raw="x",
                      project_type_id=stills.id)
    db_session.add(project)
    db_session.commit()

    generate_schedule(db_session, project)
    before = db_session.query(ProjectPhase).filter_by(project_id=project.id).all()
    before_review = next(p for p in before if p.name == "Client review")
    before_days = (before_review.end_date - before_review.start_date).days + 1

    assumption = db_session.query(Assumption).filter_by(key="client_review_days").one()
    resp = client.post(f"/assumptions/{assumption.id}/update",
                       data={"value_numeric": "10"}, follow_redirects=False)
    assert resp.status_code == 303

    db_session.expire_all()
    after = db_session.query(ProjectPhase).filter_by(project_id=project.id).all()
    after_review = next(p for p in after if p.name == "Client review")
    after_days = (after_review.end_date - after_review.start_date).days + 1

    assert after_days > before_days  # the stored phase actually changed, no manual regenerate call


def test_route_update_rate_band_persists(client, db_session):
    seed_assumptions(db_session)
    band = db_session.query(RateBand).filter_by(role=PersonRole.designer).one()

    resp = client.post(f"/assumptions/rate-bands/{band.id}/update",
                       data={"low": "400", "high": "600", "lead_time_days": "7"}, follow_redirects=False)
    assert resp.status_code == 303

    db_session.refresh(band)
    assert band.low == 400 and band.high == 600 and band.lead_time_days == 7
