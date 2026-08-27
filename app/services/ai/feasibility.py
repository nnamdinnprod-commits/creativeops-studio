from app.config import settings
from app.services.ai import client, mock
from app.services.ai.prompts import build_schedule_feasibility_prompt
from app.services.ai.schemas import ScheduleAssessment, ScheduleOption


def assess_schedule_feasibility(computed_schedule_facts: dict) -> ScheduleAssessment | None:
    if settings.ai_provider == "mock":
        result = mock.mock_assess_schedule_feasibility(computed_schedule_facts)
    else:
        prompt = build_schedule_feasibility_prompt(computed_schedule_facts)
        result = client.complete_json(prompt, ScheduleAssessment)

    if result is None:
        return None

    # Every number here is recomputed from the given facts, never trusted from the
    # response — same rule as recommend_resource's impact figures on accept. The model's
    # only real choices are which candidate to name as binding_constraint (validated
    # against what was actually offered) and the wording of statement/caveats/confidence.
    result.feasible = computed_schedule_facts.get("feasible", True)
    result.shortfall_days = computed_schedule_facts.get("shortfall_days", 0)
    result.options = [
        ScheduleOption(**opt) for opt in computed_schedule_facts.get("options", [])
    ]

    candidate_names = {
        c["phase_name"] for c in computed_schedule_facts.get("binding_constraint_candidates", [])
    }
    if result.binding_constraint not in candidate_names:
        result.binding_constraint = next(iter(candidate_names), None)

    return result
