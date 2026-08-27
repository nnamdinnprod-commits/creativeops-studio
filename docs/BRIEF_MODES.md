# Brief Assistant — Quick and Full Modes

**Status: specification for session 2. Amends the Brief Assistant in `PRODUCT_SPEC.md`.**

## The flaw being fixed

V1's brief assistant refuses to be useful until the brief is complete. Real briefs are not
complete. A producer is regularly handed *"we need a summer thing for Germany — how long,
and roughly what does it cost?"* and has to answer, because that answer is what the
conversation needs in order to continue.

A tool that responds "you are missing four fields" to that question has failed at the job.

**The change is not more input fields or toggles.** It is a change in what the tool does
when information is absent:

| Now | Instead |
|---|---|
| "72% — missing asset specs, audience, approval owner" | "8–12 working days, €X–€Y. Here is what I assumed. Change any assumption and I'll recalculate." |

Missing information should widen the range and surface an assumption, not block the answer.

---

## Quick Estimate mode

**Minimum viable input:** what kind of work, roughly how much, and which market. Nothing
else is required. A single sentence should be enough.

> "Summer social campaign for Germany, maybe six or so assets, no shoot."

**Output:**

- **Indicative duration** as a range — "8–12 working days"
- **Indicative cost** as a range, with the basis shown
- **Earliest realistic delivery**, back-scheduled from today (see `PLANNING.md`)
- **The assumption list**, every one visible and editable
- **Confidence**, with the reason

Example:

> **Indicative: 8–12 working days · €6,400–€9,200**
> Earliest delivery if started Monday: 4 September
>
> **Assumed** — 6 social statics at standard spec · no original photography · 2 client
> review rounds at 3 days each · 1 designer at standard rate · German localisation, copy
> review only
>
> **Confidence: low–medium.** Volume and asset specification are both assumed. Confirming
> the asset count would narrow this to roughly ±1 day.

That last line matters more than the estimate. It tells the producer which single question
to go and ask, which is exactly the judgement the role is hiring for.

**Every assumption is a control.** Change "6 assets" to "20" and the range recomputes.
Toggle "original photography" on and a shoot phase appears with its own lead time. This is
the toggling you asked for, in a form that requires no configuration screen: the assumptions
*are* the interface.

---

## Full Brief mode

Unchanged from `PRODUCT_SPEC.md`: paste the full brief, get structured extraction, get the
readiness rubric, create a project.

---

## The readiness score changes job

It stops being a gate and becomes a confidence band. Low readiness widens the estimate
range; it does not refuse to produce one.

**This does not weaken the production gate, and must not.** The distinction:

- A **quick estimate** is not a project. It is a scoped answer to a question. It can be
  produced from almost nothing, and can be saved for reference.
- **Converting an estimate into a project** still requires the readiness threshold from
  `PRODUCT_SPEC.md`. A project below threshold still cannot pass `ready` into production.

So the readiness-gate refusal (`check_readiness_gate` in `app/routes/pipeline.py`, alongside
`validate_transition`) stays exactly as it is. What
changes is that a producer can now get an answer *before* the brief is complete, which is
when they need it. The gate still stands where it should: between an estimate and a
commitment.

State this explicitly in the demo. "The tool will always give you a number. It will not let
you promise one."

---

## Costing

Deterministic, from `ASSUMPTIONS.md`:

```
for each phase in the scheduled template:
    for each role the phase requires:
        days × role_day_rate → line
range = sum(lines) × (low_factor, high_factor)
```

Low and high factors come from the confidence band — wider input uncertainty, wider output
range. Costs are computed in Python and shown as ranges, never as single figures, and always
labelled indicative.

Rate bands live in `ASSUMPTIONS.md` and are editable. They are stated as the studio's own
planning assumptions, not as market data.

---

## AI contract

`quick_estimate(minimal_input) -> QuickEstimate`

```json
{
  "work_type": "social",
  "inferred_volume": 6,
  "volume_confidence": "assumed",
  "markets": ["DE"],
  "localisation_required": true,
  "assumptions": [
    {"key": "asset_count", "value": 6, "source": "inferred", "editable": true},
    {"key": "original_photography", "value": false, "source": "assumed", "editable": true},
    {"key": "review_rounds", "value": 2, "source": "default", "editable": true}
  ],
  "single_best_question": "How many assets, and are they all static?",
  "confidence": "low_medium",
  "caveats": ["No deadline given; earliest delivery calculated from today"]
}
```

The model infers work type, volume and markets, and names the assumptions. **It does not
produce durations or costs** — those come from the phase template and rate card once the
assumptions are settled. Same rule as everywhere else: the model reads the request, Python
does the arithmetic.

`single_best_question` is the highest-value field in that payload. It is the tool telling a
producer where the uncertainty actually is.

---

## Out of scope

Quote documents or client-facing PDF output. Multi-currency. Margin, markup, or
profitability. Historical actuals feeding back into estimates — worth doing eventually, and
the honest thing to name as the next step, since estimates learned from delivered projects
beat estimates from assumed rates every time.
