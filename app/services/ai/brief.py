from app.config import settings
from app.services.ai import client, mock
from app.services.ai.prompts import build_brief_prompt
from app.services.ai.schemas import BriefExtraction


def analyse_brief(raw_text: str) -> BriefExtraction | None:
    if settings.ai_provider == "mock":
        return mock.mock_analyse_brief(raw_text)
    prompt = build_brief_prompt(raw_text)
    return client.complete_json(prompt, BriefExtraction)
