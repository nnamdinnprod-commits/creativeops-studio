from app.config import settings
from app.services.ai import client, mock
from app.services.ai.prompts import build_insight_prompt
from app.services.ai.schemas import ProductionRecommendation


def insight_to_action(insight_facts: dict, capacity_snapshot: list[dict]) -> ProductionRecommendation | None:
    if settings.ai_provider == "mock":
        return mock.mock_insight_to_action(insight_facts, capacity_snapshot)
    prompt = build_insight_prompt(insight_facts, capacity_snapshot)
    return client.complete_json(prompt, ProductionRecommendation)
