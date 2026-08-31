import json
from datetime import date

from app.models import (
    CreativeInsight,
    Person,
    PersonRole,
    Recommendation,
    RecommendationKind,
    RecommendationStatus,
    VariantTheme,
)
from app.services.insight import compute_insight_status, dismiss_market_insight

TODAY = date(2026, 8, 21)


def _seed_gap(db_session, market="DE"):
    """A lifestyle-vs-product gap big enough to clear GAP_THRESHOLD_PCT."""
    rows = [
        CreativeInsight(brand="Fotomera", market=market, format="social_static",
                        variant_theme=VariantTheme.lifestyle, impressions=40000, ctr=2.5,
                        engagement_rate=4.5, conversion_rate=1.4,
                        period_start=TODAY, period_end=TODAY, insight_text=None),
        CreativeInsight(brand="Fotomera", market=market, format="social_static",
                        variant_theme=VariantTheme.product_only, impressions=38000, ctr=1.0,
                        engagement_rate=1.8, conversion_rate=0.7,
                        period_start=TODAY, period_end=TODAY, insight_text=None),
    ]
    db_session.add_all(rows)
    # A design-capable person with spare capacity, so /intelligence/recommend can find a
    # candidate, and a producer -- _apply_production_action assigns the new project's
    # owner to whoever holds that role.
    db_session.add_all([
        Person(name="Priya", role=PersonRole.designer, capacity_pct=100,
              skills="layout", is_external=False),
        Person(name="Sam", role=PersonRole.producer, capacity_pct=100,
              skills="", is_external=False),
    ])
    db_session.commit()
    return rows


def test_new_insight_has_no_stored_state(db_session):
    _seed_gap(db_session)
    status = compute_insight_status(db_session, "DE")
    assert status["status"] == "new"


def test_route_requesting_same_recommendation_three_times_creates_one_record(client, db_session):
    """REVIEW_02.md P4: round 1's dedup fix reached Resources but not Creative
    Intelligence — requesting a production recommendation for the same insight used
    to create a new row every time."""
    _seed_gap(db_session)

    for _ in range(3):
        resp = client.post("/intelligence/recommend", data={"market": "DE", "brand": "Fotomera"})
        assert resp.status_code == 200

    recs = db_session.query(Recommendation).filter_by(kind=RecommendationKind.production_action).all()
    assert len(recs) == 1
    assert recs[0].status == RecommendationStatus.pending

    status = compute_insight_status(db_session, "DE")
    assert status["status"] == "recommendation_pending"
    assert status["recommendation_id"] == recs[0].id


def test_accepting_marks_the_insight_actioned_with_outcome_and_project_link(client, db_session):
    _seed_gap(db_session)
    client.post("/intelligence/recommend", data={"market": "DE", "brand": "Fotomera"})
    rec = db_session.query(Recommendation).filter_by(kind=RecommendationKind.production_action).one()

    resp = client.post(f"/recommendations/{rec.id}/accept")
    assert resp.status_code == 200

    status = compute_insight_status(db_session, "DE")
    assert status["status"] == "actioned"
    assert status["outcome_note"] is not None
    assert status["project_id"] is not None


def test_request_control_no_longer_offered_once_actioned(client, db_session):
    _seed_gap(db_session)
    client.post("/intelligence/recommend", data={"market": "DE", "brand": "Fotomera"})
    rec = db_session.query(Recommendation).filter_by(kind=RecommendationKind.production_action).one()
    client.post(f"/recommendations/{rec.id}/accept")

    resp = client.post("/intelligence/recommend", data={"market": "DE", "brand": "Fotomera"},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert "error=recommend_failed" in resp.headers["location"]

    # No second recommendation was created by the refused request.
    assert db_session.query(Recommendation).filter_by(kind=RecommendationKind.production_action).count() == 1


def test_rejecting_reverts_the_insight_to_new(client, db_session):
    _seed_gap(db_session)
    client.post("/intelligence/recommend", data={"market": "DE", "brand": "Fotomera"})
    rec = db_session.query(Recommendation).filter_by(kind=RecommendationKind.production_action).one()

    client.post(f"/recommendations/{rec.id}/reject")

    status = compute_insight_status(db_session, "DE")
    assert status["status"] == "new"


def test_dismiss_requires_a_reason(client, db_session):
    _seed_gap(db_session)
    resp = client.post("/intelligence/DE/dismiss", data={"reason": ""}, follow_redirects=False)
    assert resp.status_code == 303
    assert "error=recommend_failed" in resp.headers["location"]

    status = compute_insight_status(db_session, "DE")
    assert status["status"] == "new"


def test_dismiss_with_a_reason_sets_status_and_blocks_further_requests(client, db_session):
    _seed_gap(db_session)
    resp = client.post("/intelligence/DE/dismiss", data={"reason": "Sample too small this quarter"},
                       follow_redirects=False)
    assert resp.status_code == 303

    status = compute_insight_status(db_session, "DE")
    assert status["status"] == "dismissed"
    assert status["dismissed_reason"] == "Sample too small this quarter"

    resp2 = client.post("/intelligence/recommend", data={"market": "DE", "brand": "Fotomera"},
                        follow_redirects=False)
    assert "error=recommend_failed" in resp2.headers["location"]
    assert db_session.query(Recommendation).filter_by(kind=RecommendationKind.production_action).count() == 0


def test_dismiss_sets_reason_across_every_row_in_the_market_group(db_session):
    rows = _seed_gap(db_session, market="NL")
    ok = dismiss_market_insight(db_session, "NL", "Not a priority this cycle")
    assert ok is True
    for row in rows:
        db_session.refresh(row)
        assert row.dismissed_reason == "Not a priority this cycle"


def test_dismiss_unknown_market_returns_false(db_session):
    assert dismiss_market_insight(db_session, "ZZ", "no such market") is False


def test_recommend_page_renders_status_badges(client, db_session):
    _seed_gap(db_session)
    resp = client.get("/intelligence")
    assert resp.status_code == 200
    assert "New" in resp.text
    assert 'action="/intelligence/recommend"' in resp.text
    assert 'action="/intelligence/DE/dismiss"' in resp.text
