from app.config import settings
from app.services.ai import client, mock
from app.services.ai.prompts import build_localisation_prompt
from app.services.ai.schemas import LocalisationRisk


def check_localisation_risk(project_localisation_facts: dict) -> LocalisationRisk | None:
    if settings.ai_provider == "mock":
        return mock.mock_check_localisation_risk(project_localisation_facts)
    prompt = build_localisation_prompt(project_localisation_facts)
    return client.complete_json(prompt, LocalisationRisk)
