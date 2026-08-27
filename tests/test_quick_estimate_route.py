import json

from app.seed import seed_assumptions, seed_phase_templates


def _seed(db_session):
    seed_phase_templates(db_session)
    seed_assumptions(db_session)


def test_get_brief_defaults_to_quick_mode(client, db_session):
    resp = client.get("/brief")
    assert resp.status_code == 200
    assert "Quick Estimate" in resp.text


def test_get_brief_full_mode_still_works(client, db_session):
    resp = client.get("/brief?mode=full")
    assert resp.status_code == 200
    assert "Paste a messy real-world request" in resp.text


def test_quick_estimate_route_renders_a_computed_estimate(client, db_session):
    _seed(db_session)
    resp = client.post("/brief/quick-estimate", data={
        "raw_text": "Summer social campaign for Germany, maybe six or so assets, no shoot.",
    })
    assert resp.status_code == 200
    assert "working days" in resp.text
    assert "Single best question" in resp.text
    assert "Recalculate" in resp.text


def _extract_hidden_fields(html: str) -> dict:
    import re
    fields = {}
    for name in ["raw_text", "work_type", "markets_json", "localisation_required",
                "single_best_question", "caveats_json", "inferred_volume", "volume_confidence"]:
        m = re.search(rf'name="{name}" value="([^"]*)"', html)
        if m:
            fields[name] = m.group(1).replace("&#34;", '"').replace("&amp;", "&")
    return fields


def test_recompute_changes_the_numbers_without_a_new_ai_call(client, db_session):
    _seed(db_session)
    first = client.post("/brief/quick-estimate", data={
        "raw_text": "Summer social campaign for Germany, maybe six or so assets, no shoot.",
    })
    hidden = _extract_hidden_fields(first.text)

    small = client.post("/brief/quick-estimate/recompute", data={
        **hidden, "asset_count": "6", "review_rounds": "2", "confidence": "medium",
    })
    large = client.post("/brief/quick-estimate/recompute", data={
        **hidden, "asset_count": "40", "review_rounds": "2", "confidence": "medium",
    })

    assert small.status_code == 200 and large.status_code == 200
    assert small.text != large.text


def test_recompute_round_trips_markets_and_caveats(client, db_session):
    _seed(db_session)
    first = client.post("/brief/quick-estimate", data={
        "raw_text": "Summer social campaign for Germany, maybe six or so assets, no shoot.",
    })
    hidden = _extract_hidden_fields(first.text)
    assert json.loads(hidden["markets_json"]) == ["DE"]

    resp = client.post("/brief/quick-estimate/recompute", data={
        **hidden, "asset_count": "6", "review_rounds": "2", "confidence": "medium",
    })
    assert "DE" in resp.text
