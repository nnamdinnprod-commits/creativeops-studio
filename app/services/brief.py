"""Deterministic brief readiness scoring, per docs/AI_WORKFLOWS.md's fixed rubric.
The AI extracts fields (app/services/ai/brief.py); this file scores them. The
score is stable across runs and unit-testable — it never touches the model.
"""

from dataclasses import dataclass

from app.config import settings
from app.services.ai.schemas import BriefExtraction

RUBRIC_WEIGHTS = {
    "objective": 15,
    "audience": 10,
    "markets": 10,
    "deliverables_with_type": 15,
    "format_specs": 15,
    "deadline_confirmed": 15,
    "approval_owner": 10,
    "localisation_deadline": 10,
}

RUBRIC_BLOCKS = {
    "objective": "prioritisation",
    "audience": "creative direction",
    "markets": "localisation planning",
    "deliverables_with_type": "scoping",
    "format_specs": "effort estimation",
    "deadline_confirmed": "scheduling",
    "approval_owner": "review routing",
    "localisation_deadline": "multi-market delivery",
}

assert sum(RUBRIC_WEIGHTS.values()) == 100


@dataclass
class ReadinessResult:
    score: int
    present_fields: list[str]
    missing_fields: list[str]
    blocking_reasons: dict[str, str]


def score_readiness(extraction: BriefExtraction) -> ReadinessResult:
    # "localisation_deadline" has no dedicated field on BriefExtraction — the doc's
    # rubric names it but the extraction schema doesn't carry a separate localisation
    # deadline. Interpreted here as: not applicable if localisation isn't required;
    # otherwise satisfied only if target markets AND a confirmed deadline both exist,
    # since neither localisation nor the deliverable schedule can be planned without both.
    checks = {
        "objective": bool(extraction.objective),
        "audience": bool(extraction.audience),
        "markets": len(extraction.markets) > 0,
        "deliverables_with_type": any(d.type for d in extraction.deliverables),
        "format_specs": any(d.format_spec for d in extraction.deliverables),
        "deadline_confirmed": bool(extraction.deadline),
        "approval_owner": bool(extraction.approval_owner),
        "localisation_deadline": (
            not extraction.localisation.required
            or (bool(extraction.localisation.targets) and bool(extraction.deadline))
        ),
    }

    present = [k for k, ok in checks.items() if ok]
    missing = [k for k, ok in checks.items() if not ok]
    score = sum(RUBRIC_WEIGHTS[k] for k in present)

    return ReadinessResult(
        score=score,
        present_fields=present,
        missing_fields=missing,
        blocking_reasons={k: RUBRIC_BLOCKS[k] for k in missing},
    )


def is_ready_to_progress(score: int) -> bool:
    return score >= settings.brief_readiness_threshold
