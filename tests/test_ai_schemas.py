from unittest.mock import patch

from app.services.ai import client
from app.services.ai.risk import assess_portfolio_attention
from app.services.ai.schemas import AttentionBrief, AttentionItem


def test_invention_guard_drops_unfamiliar_project_id():
    """AI_WORKFLOWS.md: every project_id in the attention panel must appear in the
    input snapshot. A response referencing a project not passed in must be dropped,
    not rendered."""
    snapshot = [{"project_id": 12, "cause": "capacity_conflict"}]

    fabricated_response = AttentionBrief(
        headline="2 projects need intervention",
        items=[
            AttentionItem(project_id=12, severity="high", cause="capacity_conflict",
                         statement="Real project.", suggested_screen="resources"),
            AttentionItem(project_id=999, severity="high", cause="invented",
                         statement="This project was never in the input.", suggested_screen="resources"),
        ],
    )

    with patch("app.config.settings.ai_provider", "openai"), \
         patch.object(client, "complete_json", return_value=fabricated_response):
        result = assess_portfolio_attention(snapshot)

    assert result is not None
    project_ids = {item.project_id for item in result.items}
    assert project_ids == {12}
    assert 999 not in project_ids


def test_malformed_response_returns_none_not_a_traceback():
    """A response that fails schema validation must come back as None, so callers
    can render the fallback panel — never a raised exception, never raw text."""
    with patch("app.services.ai.client._raw_completion", return_value="not valid json {{{"):
        result = client.complete_json("irrelevant prompt", AttentionBrief)
    assert result is None


def test_response_with_invalid_field_value_returns_none():
    """severity must be one of low/medium/high — an out-of-range value should fail
    validation and come back as None, not silently coerce."""
    bad_payload = (
        '{"headline": "ok", "items": [{"project_id": 1, "severity": "extreme", '
        '"cause": "x", "statement": "x", "suggested_screen": "resources"}]}'
    )
    with patch("app.services.ai.client._raw_completion", return_value=bad_payload):
        result = client.complete_json("irrelevant prompt", AttentionBrief)
    assert result is None


def test_complete_json_retries_once_then_gives_up():
    calls = {"count": 0}

    def flaky(prompt, temperature):
        calls["count"] += 1
        return "still not json"

    with patch("app.services.ai.client._raw_completion", side_effect=flaky):
        result = client.complete_json("irrelevant prompt", AttentionBrief)

    assert result is None
    assert calls["count"] == 2
