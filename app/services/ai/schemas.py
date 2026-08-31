"""Pydantic models for every AI input and output, per docs/AI_WORKFLOWS.md.

Every AI response is parsed into one of these before it reaches a template. A
malformed response never reaches the UI — see client.py's parse-and-validate step.
"""

from typing import Literal

from pydantic import BaseModel


# --- 1. analyse_brief -------------------------------------------------------

class DeliverableSpec(BaseModel):
    type: str | None = None
    market: str | None = None
    format_spec: str | None = None
    quantity: int | None = None


class LocalisationNeed(BaseModel):
    required: bool = False
    source: str | None = None
    targets: list[str] = []


class BriefExtraction(BaseModel):
    objective: str | None = None
    audience: str | None = None
    markets: list[str] = []
    channels: list[str] = []
    deliverables: list[DeliverableSpec] = []
    deadline: str | None = None
    dependencies: list[str] = []
    resource_needs: list[str] = []
    localisation: LocalisationNeed = LocalisationNeed()
    approval_owner: str | None = None
    ambiguities: list[str] = []


# --- 2. assess_portfolio_attention ------------------------------------------

class AttentionItem(BaseModel):
    project_id: int
    severity: Literal["low", "medium", "high"]
    cause: str
    statement: str
    suggested_screen: str


class AttentionBrief(BaseModel):
    headline: str
    items: list[AttentionItem] = []


# --- 3. recommend_resource ---------------------------------------------------
# REVIEW_02.md P5.6: "a real decision has alternatives with different costs" — a
# ranked set of options, not a single take-it-or-leave-it action. Every option's
# kind, action, detail line, and actionable fields (who/what changes) are computed
# by deterministic Python (resources.py's _build_conflict_facts) and echoed here
# unchanged, the same discipline build_feasibility_facts()'s options already use —
# the model picks which option to recommend and writes the rationale, never the
# numbers.

class ResourceOption(BaseModel):
    label: str  # "A" / "B" / "C"
    kind: Literal["reassign", "engage_external", "move_delivery"]
    action: str  # one-line action, e.g. "Reassign to Maya"
    detail: str  # the cost/availability/lead-time line
    to_person_id: int | None = None  # reassign / engage_external
    # reassign / engage_external: the exact window to engage_person() with — for
    # engage_external this is already lead-time-adjusted (may differ from the
    # original assignment's own start), so accepting this option later applies
    # exactly the window it was recommended with, not a re-derived guess.
    start_date: str | None = None
    end_date: str | None = None
    new_deadline: str | None = None  # move_delivery only, ISO date


class ResourceRecommendation(BaseModel):
    project_id: int
    options: list[ResourceOption] = []
    recommended_label: str
    rationale: str
    confidence: Literal["low", "medium", "high"]
    caveats: list[str] = []


# --- 4. insight_to_action ----------------------------------------------------

class ProductionDeliverable(BaseModel):
    type: str
    market: str
    quantity: int
    format_spec: str | None = None


class SuggestedWindow(BaseModel):
    start: str
    end: str


class ProductionRecommendation(BaseModel):
    insight_summary: str
    recommended_action: str
    deliverables: list[ProductionDeliverable] = []
    estimated_days: float
    suggested_person_id: int
    suggested_window: SuggestedWindow
    localisation_required: bool
    localisation_note: str | None = None
    confidence: Literal["low", "medium", "high"]
    caveats: list[str] = []


# --- 5. check_localisation_risk ----------------------------------------------

class LocalisationRisk(BaseModel):
    at_risk: bool
    markets_at_risk: list[str] = []
    reason: str
    suggested_action: str
    severity: Literal["low", "medium", "high"]


# --- 6. assess_schedule_feasibility (Session B) -------------------------------

class ScheduleOption(BaseModel):
    action: str
    detail: str
    recovers_days: int


class ScheduleAssessment(BaseModel):
    feasible: bool
    shortfall_days: int = 0
    binding_constraint: str | None = None
    statement: str
    options: list[ScheduleOption] = []
    confidence: Literal["low", "medium", "high"]
    caveats: list[str] = []


# --- 7. quick_estimate (Session C) --------------------------------------------

class QuickEstimateAssumption(BaseModel):
    key: str
    # bool before float: bool is a subclass of int in Python, and Pydantic's smart-union
    # mode would otherwise coerce False/True into 0.0/1.0 if float were tried first.
    value: bool | float | str
    source: Literal["inferred", "assumed", "default"]
    editable: bool = True


class QuickEstimate(BaseModel):
    work_type: Literal["film", "event", "stills", "social"]
    inferred_volume: int
    volume_confidence: Literal["inferred", "assumed", "default"]
    markets: list[str] = []
    localisation_required: bool = False
    assumptions: list[QuickEstimateAssumption] = []
    single_best_question: str
    # ASSUMPTIONS.md's confidence bands are a 4-level scale (high/medium/low_medium/low),
    # not this app's usual 3-level Literal — quick_estimate is the one function that reads
    # ASSUMPTIONS.md directly, so it uses that scale rather than the app-wide one.
    confidence: Literal["high", "medium", "low_medium", "low"]
    caveats: list[str] = []
