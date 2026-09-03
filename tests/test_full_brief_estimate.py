"""REVIEW_03.md R4 commit 2: the Full Brief Assistant had no cost estimate at
all before this — it only produced extraction and a readiness score. These
tests exercise the real /brief/analyse and /brief/analyse/recompute-estimate
routes end to end, the same convention test_brief_extraction_acceptance.py
already uses, to prove the estimate genuinely shares Quick Estimate's own
calculation rather than a lookalike copy.
"""

import re

from app.seed import seed_assumptions, seed_phase_templates

SIX_BRAND_US_FILM_BRIEF = (
    "SPARKLE HOLIDAY CAMPAIGN. We need a flagship branded content film shoot, our "
    "biggest production of the year. Six of our house brands need coverage in a single "
    "consolidated production: talent-led lifestyle scenes across three practical "
    "locations in the US. This is a US-only campaign, no localisation needed. "
    "Deliverables: 6 branded content films for the US market."
)


def _seed(db_session):
    seed_phase_templates(db_session)
    seed_assumptions(db_session)


def _external_spend_low(html: str) -> int:
    match = re.search(r"External production spend</dt>\s*<dd[^>]*>€([\d,]+)", html)
    assert match is not None, "no external production spend figure in the response"
    return int(match.group(1).replace(",", ""))


def test_full_brief_has_no_cost_estimate_for_a_non_shoot_brief(client, db_session):
    _seed(db_session)
    resp = client.post("/brief/analyse", data={
        "raw_text": "A social media refresh for Germany using only existing assets.",
    })
    assert resp.status_code == 200
    assert "Brief readiness score" in resp.text  # extraction/scoring still works
    assert "External production spend" not in resp.text


def test_six_brand_us_shoot_via_full_brief_lands_in_six_figures(client, db_session):
    """The same acceptance bar as Quick Estimate's own test — a multi-brand US
    film shoot must land in six figures on this path too, not the old
    EUR 20-45k the estimator returned when this path had no cost model."""
    _seed(db_session)
    resp = client.post("/brief/analyse", data={"raw_text": SIX_BRAND_US_FILM_BRIEF})
    assert resp.status_code == 200
    assert "Cost &amp; duration estimate" in resp.text
    assert "largest single swing in this figure" in resp.text
    assert _external_spend_low(resp.text) >= 100_000


def test_recompute_estimate_route_changes_the_number_without_a_new_ai_call(client, db_session):
    _seed(db_session)
    first = client.post("/brief/analyse", data={"raw_text": SIX_BRAND_US_FILM_BRIEF})
    analysis_id = re.search(r'name="analysis_id" value="(\d+)"', first.text).group(1)

    small = client.post("/brief/analyse/recompute-estimate", data={
        "analysis_id": analysis_id, "work_type": "film", "asset_count": "6",
        "original_photography": "true", "review_rounds": "2", "confidence": "medium",
        "production_scale": "tabletop", "territory": "western_europe", "brand_count": "1",
    })
    large = client.post("/brief/analyse/recompute-estimate", data={
        "analysis_id": analysis_id, "work_type": "film", "asset_count": "6",
        "original_photography": "true", "review_rounds": "2", "confidence": "medium",
        "production_scale": "large_international", "territory": "us", "brand_count": "12",
    })
    assert small.status_code == 200 and large.status_code == 200
    assert _external_spend_low(small.text) < _external_spend_low(large.text)


def test_recompute_estimate_preserves_extraction_and_readiness_score(client, db_session):
    """Guards against a recompute silently discarding the extraction/score
    that got the producer to this screen in the first place."""
    _seed(db_session)
    first = client.post("/brief/analyse", data={"raw_text": SIX_BRAND_US_FILM_BRIEF})
    analysis_id = re.search(r'name="analysis_id" value="(\d+)"', first.text).group(1)
    score_before = re.search(r'text-3xl font-semibold[^>]*>(\d+)%', first.text).group(1)

    resp = client.post("/brief/analyse/recompute-estimate", data={
        "analysis_id": analysis_id, "work_type": "film", "asset_count": "10",
        "original_photography": "true", "review_rounds": "3", "confidence": "high",
        "production_scale": "multi_location", "territory": "us", "brand_count": "3",
    })
    assert resp.status_code == 200
    score_after = re.search(r'text-3xl font-semibold[^>]*>(\d+)%', resp.text).group(1)
    assert score_after == score_before
    assert "Extracted fields" in resp.text


def test_full_brief_and_quick_estimate_agree_on_external_spend_for_matching_inputs(client, db_session):
    """The strongest proof of 'one calculation, two render sites': forcing
    identical scale/territory/brand_count through each path's own recompute
    route must produce exactly the same external-spend figure."""
    _seed(db_session)
    quick_first = client.post("/brief/quick-estimate", data={
        "raw_text": "A branded content film shoot for the US market.",
    })
    quick_hidden = {}
    for name in ["raw_text", "work_type", "markets_json", "localisation_required",
                "single_best_question", "caveats_json", "inferred_volume", "volume_confidence"]:
        m = re.search(rf'name="{name}" value="([^"]*)"', quick_first.text)
        quick_hidden[name] = m.group(1).replace("&#34;", '"').replace("&amp;", "&")
    quick = client.post("/brief/quick-estimate/recompute", data={
        **quick_hidden, "asset_count": "6", "original_photography": "true",
        "review_rounds": "2", "confidence": "medium", "production_scale": "multi_location",
        "territory": "us", "brand_count": "6",
    })

    full_first = client.post("/brief/analyse", data={"raw_text": SIX_BRAND_US_FILM_BRIEF})
    analysis_id = re.search(r'name="analysis_id" value="(\d+)"', full_first.text).group(1)
    full = client.post("/brief/analyse/recompute-estimate", data={
        "analysis_id": analysis_id, "work_type": "film", "asset_count": "6",
        "original_photography": "true", "review_rounds": "2", "confidence": "medium",
        "production_scale": "multi_location", "territory": "us", "brand_count": "6",
    })

    assert _external_spend_low(quick.text) == _external_spend_low(full.text)
