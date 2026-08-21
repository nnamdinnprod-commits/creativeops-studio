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
└── localisation.py  # check_localisation_risk
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

## The five functions

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

Input: the conflict, the overloaded person's assignments, and candidate people with their
computed availability and skills. Python has already determined that candidates are
feasible; the model chooses among feasible options and explains.

```json
{
  "action": "reassign",
  "project_id": 12,
  "from_person_id": 3,
  "to_person_id": 5,
  "rationale": "Maya holds the motion skill and has 28% available Thursday–Friday.",
  "impact": {
    "from_person_new_allocation": 80,
    "to_person_new_allocation": 100,
    "deadline_protected": true
  },
  "confidence": "high",
  "caveats": ["Maya has not worked on this brand before"]
}
```

Persist as a `Recommendation` with `kind=resource_reallocation` before display. The
`impact` figures are recomputed in Python on accept — never trusted from the payload.

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
