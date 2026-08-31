from app.config import settings
from app.services.ai import client, mock
from app.services.ai.prompts import build_resource_prompt
from app.services.ai.schemas import ResourceOption, ResourceRecommendation


def recommend_resource(conflict_facts: dict) -> ResourceRecommendation | None:
    if settings.ai_provider == "mock":
        result = mock.mock_recommend_resource(conflict_facts)
    else:
        prompt = build_resource_prompt(conflict_facts)
        result = client.complete_json(prompt, ResourceRecommendation)

    if result is None:
        return None

    # REVIEW_02.md P5.6: every option's numbers come from conflict_facts, never
    # trusted from the response — same rule assess_schedule_feasibility's options
    # already follow. The model's only real choices are which option to recommend
    # (validated against what was actually offered) and the rationale/caveats text.
    result.project_id = conflict_facts["project_id"]
    result.options = [ResourceOption(**opt) for opt in conflict_facts.get("options", [])]
    labels = {opt.label for opt in result.options}
    if result.recommended_label not in labels:
        result.recommended_label = next(iter(labels), "")
    return result
