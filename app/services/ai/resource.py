from app.config import settings
from app.services.ai import client, mock
from app.services.ai.prompts import build_resource_prompt
from app.services.ai.schemas import ResourceRecommendation


def recommend_resource(conflict_facts: dict) -> ResourceRecommendation | None:
    if settings.ai_provider == "mock":
        return mock.mock_recommend_resource(conflict_facts)
    prompt = build_resource_prompt(conflict_facts)
    return client.complete_json(prompt, ResourceRecommendation)
