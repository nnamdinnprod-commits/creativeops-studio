from unittest.mock import patch

from app.services.ai import client, mock
from app.services.ai.estimate import quick_estimate
from app.services.ai.schemas import QuickEstimate


def test_mock_matches_the_worked_example_shape():
    result = mock.mock_quick_estimate(
        "Summer social campaign for Germany, maybe six or so assets, no shoot."
    )
    assert result.work_type == "social"
    assert result.inferred_volume == 6
    assert result.volume_confidence == "assumed"  # hedged ("or so"), not a firm count
    assert "DE" in result.markets
    assert result.localisation_required is True

    by_key = {a.key: a for a in result.assumptions}
    assert by_key["original_photography"].value is False
    assert by_key["original_photography"].source == "inferred"  # "no shoot" is explicit
    assert "No deadline given" in " ".join(result.caveats)


def test_mock_falls_back_to_defaults_on_a_sparse_request():
    result = mock.mock_quick_estimate("Need some social assets soon.")
    by_key = {a.key: a for a in result.assumptions}
    assert by_key["asset_count"].value == 6
    assert by_key["asset_count"].source == "assumed"
    assert result.markets == []
    assert result.localisation_required is False


def test_mock_infers_event_and_film_work_types():
    assert mock.mock_quick_estimate("A live activation event for a product launch.").work_type == "event"
    assert mock.mock_quick_estimate("A branded content video for the brand.").work_type == "film"


def test_mock_single_best_question_targets_the_weakest_assumption():
    vague = mock.mock_quick_estimate("Some social content, not sure how much.")
    assert "how many assets" in vague.single_best_question.lower()


def test_quick_estimate_uses_mock_when_provider_is_mock():
    with patch("app.config.settings.ai_provider", "mock"):
        result = quick_estimate("Social campaign for France, 10 assets.")
    assert isinstance(result, QuickEstimate)
    assert result.work_type == "social"


def test_malformed_live_response_returns_none():
    with patch("app.services.ai.client._raw_completion", return_value="not valid json {{{"):
        result = client.complete_json("irrelevant prompt", QuickEstimate)
    assert result is None
