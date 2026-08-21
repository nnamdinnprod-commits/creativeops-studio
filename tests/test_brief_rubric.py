from app.services.ai.schemas import BriefExtraction, DeliverableSpec, LocalisationNeed
from app.services.brief import RUBRIC_WEIGHTS, is_ready_to_progress, score_readiness


def test_rubric_weights_sum_to_100():
    assert sum(RUBRIC_WEIGHTS.values()) == 100


def test_fully_complete_brief_scores_100():
    extraction = BriefExtraction(
        objective="Refresh winter hero creative",
        audience="Existing NL customers",
        markets=["NL", "DE"],
        channels=["paid_social"],
        deliverables=[DeliverableSpec(type="social_static", market="NL", format_spec="1080x1080", quantity=4)],
        deadline="2026-09-04",
        approval_owner="Sam",
        localisation=LocalisationNeed(required=True, source="NL", targets=["DE"]),
    )
    result = score_readiness(extraction)
    assert result.score == 100
    assert result.missing_fields == []


def test_empty_brief_scores_only_the_not_applicable_localisation_credit():
    """An empty brief defaults localisation.required to False, so that one
    criterion is trivially satisfied (nothing to localise) rather than failed —
    it earns its 10 points while everything else is genuinely missing."""
    extraction = BriefExtraction()
    result = score_readiness(extraction)
    assert result.score == 10
    assert result.present_fields == ["localisation_deadline"]
    assert set(result.missing_fields) == set(RUBRIC_WEIGHTS.keys()) - {"localisation_deadline"}


def test_vague_brief_scores_in_expected_band():
    """Mirrors the seed 'Loyalty App Push' brief: objective and markets present,
    but no confirmed deadline, audience, format specs, or approval owner."""
    extraction = BriefExtraction(
        objective="Need something for the app push",
        audience=None,
        markets=["DE"],
        deliverables=[DeliverableSpec(type=None, market=None, format_spec=None, quantity=None)],
        deadline=None,
        approval_owner=None,
        localisation=LocalisationNeed(required=False),
    )
    result = score_readiness(extraction)
    # objective (15) + markets (10) + localisation_deadline n/a (10) = 35
    assert result.score == 35
    assert "deadline_confirmed" in result.missing_fields
    assert result.blocking_reasons["deadline_confirmed"] == "scheduling"


def test_localisation_deadline_check_requires_both_targets_and_deadline():
    extraction = BriefExtraction(
        localisation=LocalisationNeed(required=True, source="NL", targets=["FR"]),
        deadline=None,
    )
    result = score_readiness(extraction)
    assert "localisation_deadline" in result.missing_fields

    extraction2 = extraction.model_copy(update={"deadline": "2026-09-04"})
    result2 = score_readiness(extraction2)
    assert "localisation_deadline" not in result2.missing_fields


def test_is_ready_to_progress_uses_threshold():
    assert is_ready_to_progress(70) is True
    assert is_ready_to_progress(69) is False
