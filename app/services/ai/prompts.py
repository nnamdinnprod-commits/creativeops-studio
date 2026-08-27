"""Prompt templates, versioned per docs/AI_WORKFLOWS.md. Bump the version constant
and note it in docs/DECISIONS.md whenever a prompt changes materially.
"""

import json

PROMPT_VERSION = "v1"

_FOOTER = (
    "\n\nRespond with a single JSON object only — no prose, no markdown fences. "
    "Do not invent or recalculate any fact given above; use only what is provided. "
    "If the facts are insufficient for a confident recommendation, say so in "
    "`caveats` and set `confidence` to `low`. Do not fill gaps with assumptions."
)


def build_brief_prompt(raw_text: str) -> str:
    return (
        "You are a creative operations assistant extracting structure from a messy "
        "creative production request. Extract only what is stated or clearly implied — "
        "do not score readiness, that is computed separately.\n\n"
        f"Raw request:\n{raw_text}\n\n"
        "Return an object with fields: objective, audience, markets (list of ISO-ish "
        "market codes), channels, deliverables (list of {type, market, format_spec, "
        "quantity}), deadline (date string or null if unconfirmed), dependencies, "
        "resource_needs, localisation ({required, source, targets}), approval_owner, "
        "ambiguities (list of specific phrases that are vague or unconfirmed)."
        + _FOOTER
    )


def build_attention_prompt(snapshot: list[dict]) -> str:
    return (
        "You are a creative operations assistant writing a dashboard 'needs attention' "
        "panel for a producer. The following projects have already been identified by "
        "deterministic Python logic as needing intervention — do not add or remove any "
        "project from this list, only phrase why each one matters.\n\n"
        f"Qualifying projects (JSON):\n{json.dumps(snapshot, default=str)}\n\n"
        "Return an object with: headline (a one-line summary of how many projects need "
        "attention this week), items (list of {project_id, severity, cause, statement, "
        "suggested_screen}). Every project_id in items MUST be one of the project_id "
        "values given above — never reference a project not listed."
        + _FOOTER
    )


def build_resource_prompt(conflict_facts: dict) -> str:
    return (
        "You are a creative operations assistant recommending a resource reassignment. "
        "The overloaded person and the feasible candidates below have already been "
        "determined by deterministic Python — you are choosing among the feasible "
        "candidates given and explaining the choice, not inventing new ones.\n\n"
        f"Conflict and candidates (JSON):\n{json.dumps(conflict_facts, default=str)}\n\n"
        "Return an object with: action ('reassign'), project_id, from_person_id, "
        "to_person_id (must be one of the candidate person_id values given), rationale, "
        "impact ({from_person_new_allocation, to_person_new_allocation, "
        "deadline_protected}), confidence, caveats."
        + _FOOTER
    )


def build_insight_prompt(insight_facts: dict, capacity_snapshot: list[dict]) -> str:
    return (
        "You are a creative operations assistant turning a creative performance insight "
        "into a scheduleable production recommendation. The insight numbers and the "
        "candidate people's availability below are already computed by deterministic "
        "Python — use them as given facts.\n\n"
        f"Insight (JSON):\n{json.dumps(insight_facts, default=str)}\n\n"
        f"Candidate people (JSON):\n{json.dumps(capacity_snapshot, default=str)}\n\n"
        "Return an object with: insight_summary, recommended_action, deliverables "
        "(list of {type, market, quantity, format_spec}), estimated_days, "
        "suggested_person_id (must be one of the candidate person_id values given), "
        "suggested_window ({start, end}), localisation_required, localisation_note, "
        "confidence, caveats. If the sample size behind the insight is small, say so "
        "explicitly in caveats."
        + _FOOTER
    )


def build_localisation_prompt(project_localisation_facts: dict) -> str:
    return (
        "You are a creative operations assistant explaining a localisation risk. "
        "Whether the project is at risk has already been determined by deterministic "
        "Python — you are phrasing the reason and suggesting an action, not deciding "
        "at_risk yourself; echo the given at_risk value exactly.\n\n"
        f"Facts (JSON):\n{json.dumps(project_localisation_facts, default=str)}\n\n"
        "Return an object with: at_risk (echo the given value exactly), "
        "markets_at_risk, reason, suggested_action, severity."
        + _FOOTER
    )


def build_schedule_feasibility_prompt(computed_schedule_facts: dict) -> str:
    return (
        "You are a creative operations assistant assessing whether a generated production "
        "schedule fits its deadline. Feasibility, the shortfall in working days, the "
        "candidate binding constraints, and every option's recovered days have already "
        "been computed by deterministic Python — you are choosing which one candidate best "
        "explains the shortfall and writing one clear, specific sentence a producer can "
        "act on, not deciding feasibility or inventing a phase or a day count yourself.\n\n"
        f"Computed facts (JSON):\n{json.dumps(computed_schedule_facts, default=str)}\n\n"
        "Return an object with: feasible (echo the given value exactly), shortfall_days "
        "(echo exactly), binding_constraint (must be exactly one of the given "
        "binding_constraint_candidates' phase_name values, or null if feasible is true), "
        "statement (name the working-day shortfall and the binding constraint in plain "
        "language), options (echo the given options list exactly — same items, same order, "
        "same recovers_days — do not add, remove, or reword any), confidence, caveats."
        + _FOOTER
    )
