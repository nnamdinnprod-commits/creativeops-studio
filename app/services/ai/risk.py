from app.config import settings
from app.services.ai import client, mock
from app.services.ai.prompts import build_attention_prompt
from app.services.ai.schemas import AttentionBrief


def assess_portfolio_attention(snapshot: list[dict]) -> AttentionBrief | None:
    if settings.ai_provider == "mock":
        result = mock.mock_assess_portfolio_attention(snapshot)
    else:
        prompt = build_attention_prompt(snapshot)
        result = client.complete_json(prompt, AttentionBrief)

    if result is None:
        return None

    # Invention guard: drop any item referencing a project not in the input snapshot.
    valid_ids = {entry["project_id"] for entry in snapshot}
    result.items = [item for item in result.items if item.project_id in valid_ids]
    return result
