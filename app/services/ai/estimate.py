from app.config import settings
from app.services.ai import client, mock
from app.services.ai.prompts import build_quick_estimate_prompt
from app.services.ai.schemas import QuickEstimate


def quick_estimate(raw_text: str) -> QuickEstimate | None:
    if settings.ai_provider == "mock":
        return mock.mock_quick_estimate(raw_text)
    prompt = build_quick_estimate_prompt(raw_text)
    return client.complete_json(prompt, QuickEstimate)
