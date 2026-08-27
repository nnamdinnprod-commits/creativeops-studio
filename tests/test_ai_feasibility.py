from unittest.mock import patch

from app.services.ai import client, mock
from app.services.ai.feasibility import assess_schedule_feasibility
from app.services.ai.schemas import ScheduleAssessment, ScheduleOption

FEASIBLE_FACTS = {"feasible": True}

INFEASIBLE_FACTS = {
    "feasible": False,
    "shortfall_days": 5,
    "delivery_date": "2026-09-14",
    "project_start": "2026-09-03",
    "binding_constraint_candidates": [
        {"phase_name": "Client review", "working_days": 4},
        {"phase_name": "Revisions", "working_days": 2},
    ],
    "options": [
        {"action": "compress_review", "detail": "Client review 4 days to 2", "recovers_days": 2},
        {"action": "move_delivery", "detail": "to 2026-09-21", "recovers_days": 5},
    ],
}


def test_mock_feasible_has_no_options_or_binding_constraint():
    result = mock.mock_assess_schedule_feasibility(FEASIBLE_FACTS)
    assert result.feasible is True
    assert result.binding_constraint is None
    assert result.options == []


def test_mock_infeasible_names_the_top_candidate_and_echoes_options():
    result = mock.mock_assess_schedule_feasibility(INFEASIBLE_FACTS)
    assert result.feasible is False
    assert result.shortfall_days == 5
    assert result.binding_constraint == "Client review"
    assert "5 working days" in result.statement
    assert [o.action for o in result.options] == ["compress_review", "move_delivery"]


def test_invention_guard_rejects_a_binding_constraint_not_in_candidates():
    """The model must only name a binding constraint Python actually offered."""
    fabricated = ScheduleAssessment(
        feasible=False, shortfall_days=5, binding_constraint="Fabrication & build (invented)",
        statement="Fabricated statement.",
        options=[ScheduleOption(action="move_delivery", detail="to 2026-09-21", recovers_days=5)],
        confidence="high", caveats=[],
    )
    with patch("app.config.settings.ai_provider", "openai"), \
         patch.object(client, "complete_json", return_value=fabricated):
        result = assess_schedule_feasibility(INFEASIBLE_FACTS)

    assert result is not None
    assert result.binding_constraint in {"Client review", "Revisions"}
    assert result.binding_constraint != "Fabrication & build (invented)"


def test_numeric_fields_are_overwritten_from_facts_not_trusted_from_the_model():
    """Same rule as recommend_resource's impact figures: the model's numbers never win."""
    fabricated = ScheduleAssessment(
        feasible=True, shortfall_days=999, binding_constraint="Client review",
        statement="Wrong statement.",
        options=[ScheduleOption(action="invented", detail="made up", recovers_days=999)],
        confidence="high", caveats=[],
    )
    with patch("app.config.settings.ai_provider", "openai"), \
         patch.object(client, "complete_json", return_value=fabricated):
        result = assess_schedule_feasibility(INFEASIBLE_FACTS)

    assert result.feasible is False  # from INFEASIBLE_FACTS, not the model's True
    assert result.shortfall_days == 5  # from INFEASIBLE_FACTS, not 999
    assert [o.action for o in result.options] == ["compress_review", "move_delivery"]


def test_malformed_response_returns_none():
    with patch("app.services.ai.client._raw_completion", return_value="not valid json {{{"):
        result = client.complete_json("irrelevant prompt", ScheduleAssessment)
    assert result is None
