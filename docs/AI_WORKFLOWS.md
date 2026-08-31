# AI Architecture and Workflows

## The governing rule

**Python computes. The model explains and proposes.**

Any number shown to a user — utilisation, readiness score, days available, CTR difference
— is calculated in deterministic Python and passed *into* the prompt as given facts. The
model is never the source of a figure. This makes the demo reproducible, unit-testable,
and honest about where the intelligence actually lives.

A reviewer who asks "what happens if the model hallucinates?" should get the answer: the
numbers can't move, only the wording.

## Structure

```
app/services/ai/
├── client.py        # provider abstraction — the only file importing an LLM SDK
├── schemas.py       # Pydantic models for every AI input and output
├── prompts.py       # prompt templates, versioned
├── mock.py          # mock implementation of every function, identical shapes
├── brief.py         # analyse_brief
├── risk.py          # assess_portfolio_attention, assess_project_risk
├── resource.py      # recommend_resource
├── insight.py       # insight_to_action
├── localisation.py  # check_localisation_risk
├── feasibility.py   # assess_schedule_feasibility (Session B, DECISIONS.md 022)
└── estimate.py      # quick_estimate (Session C, DECISIONS.md 026)
```

`client.py` exposes one function:

```python
def complete_json(prompt: str, schema: type[BaseModel], *, temperature: float = 0.2) -> BaseModel | None
```

It selects provider from settings (`AI_PROVIDER`: `openai` / `anthropic` / `mock`), sends
the request, parses the response as JSON, validates against `schema`, and returns `None` on
any failure. One retry on a validation failure, then give up. No provider SDK is imported
anywhere else in the codebase.

## Demo mode

With no API key set, or `AI_PROVIDER=mock`, every function returns a curated mock response
from `mock.py`. The mocks must be good — the demo may well be given on a train with no
connectivity, and a reviewer should not be able to tell which mode is running except by
the mode indicator in the footer.

Mock responses are keyed to the seed data so they remain coherent with what is on screen.

## Failure behaviour

When an AI call fails or returns `None`, the panel shows a plain fallback: what it would
have contained, and a retry control. Never a traceback, never raw model output, never an
empty box. Deterministic facts still render — a failed narration must not hide the
underlying numbers.

---

## The functions

Five from V1, plus `assess_schedule_feasibility` (Session B) and `quick_estimate`
(Session C).

### 1. `analyse_brief(raw_text) -> BriefExtraction`

Extracts structure from a messy request. **Extraction only — it does not score.**

```json
{
  "objective": "string | null",
  "audience": "string | null",
  "markets": ["DE", "FR"],
  "channels": ["paid_social", "homepage"],
  "deliverables": [
    {"type": "social_static", "market": "DE", "format_spec": null, "quantity": 6}
  ],
  "deadline": "2026-09-04 | null",
  "dependencies": ["product photography not yet shot"],
  "resource_needs": ["designer", "motion_designer"],
  "localisation": {"required": true, "source": "EN", "targets": ["DE", "FR"]},
  "approval_owner": "string | null",
  "ambiguities": ["'ideally next Friday' — not a confirmed date"]
}
```

`app/services/brief.py` then computes readiness from a fixed rubric:

| Field | Weight | Blocks |
|---|---|---|
| objective | 15 | prioritisation |
| audience | 10 | creative direction |
| markets | 10 | localisation planning |
| deliverables with type | 15 | scoping |
| format specs | 15 | effort estimation |
| deadline (confirmed) | 15 | scheduling |
| approval owner | 10 | review routing |
| localisation deadline | 10 | multi-market delivery |

Score = sum of weights for fields present. Below 70 the project cannot leave `ready`.
Weights live in one constant so the rubric is visible and adjustable.

### 2. `assess_portfolio_attention(snapshot) -> AttentionBrief`

Powers the dashboard panel. Input is a computed snapshot — Python has already decided
which projects qualify and why.

```json
{
  "headline": "3 projects need intervention this week",
  "items": [
    {
      "project_id": 12,
      "severity": "high",
      "cause": "capacity_conflict",
      "statement": "Campaign X is at risk — Alex is at 95% against a Friday deadline",
      "suggested_screen": "resources"
    }
  ]
}
```

Every `project_id` must appear in the input snapshot. Validate this after parsing and drop
any item referencing a project that was not passed in — the cheapest possible guard against
invention.

### 3. `recommend_resource(conflict_facts) -> ResourceRecommendation`

REVIEW_02.md P5.6: "a real decision has alternatives with different costs" — a ranked set
of options, not a single take-it-or-leave-it action. Input: the conflict and every option
Python already knows how to build — reassign to a Team member, engage an external Talent
Pool member (REVIEW_02.md P5.5, with real cost/lead-time figures from `RateBand`), or move
the delivery date (the days needed to clear the actual overlap, always computable). The
model picks which one to recommend and writes the rationale; every option's numbers are
computed before the call and overwritten from those facts after parsing (same discipline as
`assess_schedule_feasibility`'s `options` field) — never trusted from the response.

```json
{
  "project_id": 12,
  "options": [
    {"label": "A", "kind": "reassign", "action": "Reassign to Maya",
     "detail": "no cost, available 2026-09-03, has worked this brand before",
     "to_person_id": 5, "start_date": "2026-09-03", "end_date": "2026-09-10"},
    {"label": "B", "kind": "engage_external", "action": "Engage Lars (external, motion designer)",
     "detail": "€550/day × 6 days, 5-day lead time, available 2026-09-05",
     "to_person_id": 9, "start_date": "2026-09-05", "end_date": "2026-09-10"},
    {"label": "C", "kind": "move_delivery", "action": "Move delivery to 18 Sep",
     "detail": "no cost, no resource change, client conversation required",
     "new_deadline": "2026-09-18"}
  ],
  "recommended_label": "A",
  "rationale": "Maya has spare capacity and needs no lead time — the fastest, no-cost way to bring Alex back under 80%.",
  "confidence": "high",
  "caveats": []
}
```

Persist as a `Recommendation` with `kind=resource_reallocation` before display; each option
gets its own Accept control (`app/routes/recommendations.py`'s `accept()` takes
`option_label`, defaulting to `recommended_label` if none is posted) — the human may accept
any option, not only the recommended one. `engage_external`'s effect routes through
`app/services/assignment.py::engage_person()` (REVIEW_02.md P5.5's "one mechanism, three
screens"), re-checking capacity and lead time at accept time. `move_delivery`'s effect
shifts both `Project.deadline` and the overloaded person's assignment by the same number of
days — the actual mechanism that resolves the conflict, not just a date-field update.

### 4. `insight_to_action(insight_facts, capacity_snapshot) -> ProductionRecommendation`

The centrepiece. Turns a performance observation into schedulable work.

```json
{
  "insight_summary": "Lifestyle-led creative outperforms product-only in Germany (CTR 2.4% vs 1.1%, n=6 variants)",
  "recommended_action": "Produce 3 additional lifestyle-led variants for the German market",
  "deliverables": [
    {"type": "social_static", "market": "DE", "quantity": 3, "format_spec": "1080x1080"}
  ],
  "estimated_days": 2.0,
  "suggested_person_id": 5,
  "suggested_window": {"start": "2026-09-03", "end": "2026-09-04"},
  "localisation_required": true,
  "localisation_note": "German copy review required before publish",
  "confidence": "medium",
  "caveats": ["Sample size is small; treat as directional"]
}
```

Accepting creates a Project at status `ready`, its Deliverables, the Assignment, and the
Localisation row, in one transaction.

The `caveats` field is not decoration. A recommendation drawn from six variants should say
so — that restraint is exactly the operational judgement the portfolio piece is meant to
demonstrate.

### 5. `check_localisation_risk(project_localisation_facts) -> LocalisationRisk`

```json
{
  "at_risk": true,
  "markets_at_risk": ["FR"],
  "reason": "French review has no assigned reviewer with 4 days to deadline",
  "suggested_action": "Assign a French reviewer today or move the FR deadline",
  "severity": "high"
}
```

The `at_risk` determination is made in Python first; the model supplies phrasing and the
suggested action.

### 6. `assess_schedule_feasibility(computed_schedule_facts) -> ScheduleAssessment` (Session B)

Wired into `/timeline` (per project) and `/dashboard`'s Schedule tile. See `docs/PLANNING.md`
"What the AI does here" for the full spec and `docs/DECISIONS.md` 022 for what's built.

```json
{
  "feasible": false,
  "shortfall_days": 30,
  "binding_constraint": "Pre-production",
  "statement": "Working backwards from the deadline, this project needed to start 2026-07-16 — 30 working days ago. Pre-production (8 working days) is the largest single contributor.",
  "options": [
    {"action": "compress_review", "detail": "Client review 1 3 days to 2", "recovers_days": 1},
    {"action": "drop_revisions", "detail": "drop Revisions (2 days)", "recovers_days": 2},
    {"action": "move_delivery", "detail": "to 2026-10-19", "recovers_days": 30}
  ],
  "confidence": "high",
  "caveats": []
}
```

`feasible`, `shortfall_days`, and every `options` entry are computed by
`app/services/scheduling.py`'s `build_feasibility_facts()` (compression order: review
windows first, then revision phases — never a fabrication lead time or an anchored phase)
and overwritten from those facts after parsing, exactly like `recommend_resource`'s `impact`
figures on accept — the model cannot move a number. The model's only real choices are which
of the given `binding_constraint_candidates` to name as `binding_constraint` (validated
after parsing; an unfamiliar name falls back to Python's top candidate) and the wording of
`statement`/`caveats`/`confidence`. Only called for a project whose schedule doesn't fit its
deadline — a feasible schedule has nothing to narrate, so no call is made and no panel shows.

"Overlap phases that don't strictly depend on each other" (`PLANNING.md`'s third compression
priority) isn't computed — it needs a phase dependency graph this data model doesn't have.
Not attempted rather than faked.

### 7. `quick_estimate(raw_text) -> QuickEstimate` (Session C)

Wired into `/brief` (the default mode). See `docs/BRIEF_MODES.md` for the full spec and
`docs/DECISIONS.md` 026 for what's built vs. simplified.

```json
{
  "work_type": "social",
  "inferred_volume": 6,
  "volume_confidence": "assumed",
  "markets": ["DE"],
  "localisation_required": true,
  "assumptions": [
    {"key": "asset_count", "value": 6, "source": "assumed", "editable": true},
    {"key": "original_photography", "value": false, "source": "inferred", "editable": true},
    {"key": "review_rounds", "value": 2, "source": "default", "editable": true}
  ],
  "single_best_question": "How many assets, and are they all static?",
  "confidence": "low_medium",
  "caveats": ["No deadline given; earliest delivery is calculated from today."]
}
```

Unlike every other function here, this one doesn't narrate around Python-computed facts —
it's the extraction step, closer in shape to `analyse_brief` (function 1). It reads raw text
and infers the request's shape; `app/services/estimate.py`'s `compute_estimate()` is what
turns the settled assumptions into a duration, a cost range, and an earliest delivery date.
Recomputing after a producer edits a control (asset count, the photography toggle, review
rounds, or confidence) never calls this function again — it's pure Python from there, reading
`Assumption`/`RateBand` live.

`work_type` is constrained to the four seeded `ProjectType` names; `confidence` uses
`ASSUMPTIONS.md`'s 4-level scale, not this doc's usual 3-level one.

---

## Prompt conventions

- Every prompt states: the role, the given facts as JSON, the required output schema, and
  an explicit instruction that facts must not be invented or recalculated.
- Every prompt ends with: *"If the facts are insufficient for a confident recommendation,
  say so in `caveats` and set `confidence` to `low`. Do not fill gaps with assumptions."*
- Temperature 0.2 default. Nothing here benefits from creative variance.
- Prompts are versioned with a constant. When a prompt changes materially, bump it and note
  it in `DECISIONS.md`.

## Testing the AI layer

- Schema validation tests use recorded fixture responses, including deliberately malformed
  ones — assert the fallback renders and nothing raises.
- The invention guard (function 2) has a test feeding a response referencing a project not
  in the input, asserting it is dropped.
- Rubric scoring is tested directly with no model involved.
- No test makes a live API call.
