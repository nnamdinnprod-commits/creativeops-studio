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


def test_mock_extracts_us_as_a_market():
    """REVIEW_03.md R4: 'US' extracted as nothing was its own small bug,
    independent of the cost model -- any non-EU market used to vanish."""
    result = mock.mock_quick_estimate("A branded content film for the US market.")
    assert "US" in result.markets


def test_mock_does_not_confuse_a_bare_number_word_for_asset_count_when_it_names_brands():
    """Regression: 'six brands' used to be misread as asset_count=6."""
    result = mock.mock_quick_estimate(
        "A branded content film shoot for six brands, talent-led, multiple locations."
    )
    by_key = {a.key: a for a in result.assumptions}
    assert by_key["asset_count"].source == "assumed"  # no real asset count stated here
    assert by_key["brand_count"].value == 6
    assert by_key["brand_count"].source == "inferred"


def test_mock_infers_production_scale_territory_and_brand_count_only_for_a_shoot():
    """REVIEW_03.md R4: these three only mean anything once a shoot is
    confirmed -- a non-shoot brief never grows them at all."""
    no_shoot = mock.mock_quick_estimate("Summer social campaign for Germany, no shoot.")
    keys = {a.key for a in no_shoot.assumptions}
    assert "production_scale" not in keys
    assert "territory" not in keys
    assert "brand_count" not in keys

    shoot = mock.mock_quick_estimate(
        "A branded content film, multi-location talent-led shoot for 4 brands in the US market."
    )
    by_key = {a.key: a for a in shoot.assumptions}
    assert by_key["production_scale"].value == "multi_location"
    assert by_key["production_scale"].source == "inferred"
    assert by_key["territory"].value == "us"
    assert by_key["territory"].source == "inferred"
    assert by_key["brand_count"].value == 4
    assert by_key["brand_count"].source == "inferred"


def test_mock_falls_back_to_assumed_scale_and_territory_when_the_text_is_silent():
    """REVIEW_03.md R4: 'don't let inference carry the acceptance case' — when
    the brief gives no clean signal, these default rather than guess wildly,
    and the gap is flagged as a caveat."""
    result = mock.mock_quick_estimate("A branded content film shoot for the brand.")
    by_key = {a.key: a for a in result.assumptions}
    assert by_key["production_scale"].source == "assumed"
    assert by_key["territory"].source == "assumed"
    assert by_key["brand_count"].source == "assumed"
    assert by_key["brand_count"].value == 1
    joined_caveats = " ".join(result.caveats)
    assert "Production scale assumed" in joined_caveats
    assert "Territory assumed" in joined_caveats
    assert "Brand count assumed" in joined_caveats


def test_mock_large_international_scale_requires_genuine_cross_border_language():
    """'Flagship'/'biggest production of the year' describe importance, not
    geography — a big domestic shoot must not be misread as international."""
    domestic = mock.mock_quick_estimate(
        "Our flagship film shoot, the biggest production of the year, talent-led, "
        "multiple locations, US-only campaign."
    )
    by_key = {a.key: a for a in domestic.assumptions}
    assert by_key["production_scale"].value == "multi_location"

    international = mock.mock_quick_estimate(
        "A talent-led international film shoot across multiple locations."
    )
    by_key = {a.key: a for a in international.assumptions}
    assert by_key["production_scale"].value == "large_international"
