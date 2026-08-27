# Assumptions Library

**Status: built and live.** The table, seed, and editable screen (`/assumptions`) are Session
C step 1 (`DECISIONS.md` 025); Quick Estimate mode (`/brief`, `app/services/estimate.py`) is
Session C steps 2–4 (`DECISIONS.md` 026) and is the real consumer — editing a value on
`/assumptions` and recomputing an open estimate now genuinely changes the numbers, no code
change required. `PLANNING.md`'s back-scheduling (`app/services/scheduling.py`, Session B)
is the one thing in the app that still reads its own hardcoded constants rather than this
table — a deliberate, documented gap (`DECISIONS.md` 025), not an oversight.

## What this is

An editable, visible table of the studio's own production planning assumptions. Review cycle
lengths, lead times, day rate bands, volume scaling. It feeds scheduling (`PLANNING.md`) and
estimation (`BRIEF_MODES.md`), and every number it holds can be changed by the user.

## What this deliberately is not

It is **not** a production intelligence database. It does not contain, and must not appear
to contain, union rules, right-to-work regulations, filming permissions by country, tax
incentive schemes, or any other regulatory or legal information.

That restriction is deliberate and worth stating plainly, because the temptation runs the
other way. A tool that tells a producer what is permissible to film in a given country is
genuinely valuable — and a tool that tells them *incorrectly* is worse than no tool, because
it will be believed. Any version of that data buildable in a day would be invented, stale,
or both, and it would be circulating in a portfolio piece among people who work in the
industry and would act on it.

The honest position: encode professional judgement, label it as judgement, and name the real
thing as the roadmap.

**In the presentation, say this:** *"The scheduling and costing run on an editable
assumptions library — my own production heuristics, visible and adjustable rather than
buried. The natural next step is grounding these in real production intelligence: trade
body data, film commission requirements, business affairs and union constraints by market.
That's a data partnership problem, not a code problem, which is why the prototype models it
as assumptions rather than pretending to have the data."*

Naming what is missing reads as judgement. Faking it reads as the opposite, and to this
audience it reads as the opposite immediately.

---

## Categories

### Review and approval cycles

| Key | Default | Notes |
|---|---|---|
| `client_review_days` | 3 | per round |
| `client_review_minimum_days` | 2 | floor when compressing |
| `internal_review_days` | 1 | |
| `default_review_rounds` | 2 | |
| `localisation_review_days` | 2 | per market |

### Lead times

| Key | Default | Notes |
|---|---|---|
| `fabrication_lead_days` | 15 | events — usually the binding constraint |
| `talent_booking_lead_days` | 10 | |
| `location_permit_lead_days` | 12 | varies enormously by market; a planning figure only |
| `translation_turnaround_days` | 3 | per market, standard volume |

### Day rate bands

Stated as ranges, in euros, as planning figures.

| Role | Low | High |
|---|---|---|
| Producer | 450 | 650 |
| Senior Designer | 500 | 700 |
| Designer | 350 | 500 |
| Motion Designer | 450 | 650 |
| Copywriter | 400 | 550 |
| Translator (external) | 300 | 450 |

### Volume scaling

Deliberately sub-linear — setup cost is fixed, so twenty assets do not take three times as
long as six.

| Asset count | Factor |
|---|---|
| 1–6 | 1.0 |
| 7–15 | 1.6 |
| 16–30 | 2.5 |
| 31–60 | 3.8 |

### Confidence bands

How input uncertainty widens an output range.

| Confidence | Low factor | High factor |
|---|---|---|
| high | 0.95 | 1.10 |
| medium | 0.85 | 1.25 |
| low_medium | 0.75 | 1.40 |
| low | 0.60 | 1.70 |

---

## Interface

**Built** (`/assumptions`) — a single editable table, grouped by category. Each row shows
key, current value, default, and a short note on what it affects. "Changing a value
recomputes any open estimate or schedule immediately" is true for a Quick Estimate — edit a
value here, then hit Recalculate on `/brief`'s Quick Estimate tab, and the range moves.
Generated project schedules (`PLANNING.md`'s back-scheduling) are the one exception: they
still read `app/services/scheduling.py`'s own hardcoded constants, not this table.

The "Confidence bands" table above is two numbers per row (low/high factor per band); the
editable table flattens that into one row per number — `confidence_high_low_factor`,
`confidence_high_high_factor`, and so on — since `ASSUMPTIONS.md`'s own data model gives
every `Assumption` row a single `value_numeric`, not a pair.

A "reset to defaults" control, because a demo will be run several times and someone will
have been experimenting. Built — resets every `Assumption` row's `value_numeric` to its
`default_value`. `RateBand` isn't part of the reset (see Data model below).

## Labelling rule

Every screen fed by this library carries the line:

> Planning assumptions — editable studio defaults, not regulatory or market data.

This sits alongside, not instead of, the standard disclaimer in `POSITIONING.md`.

## Data model

```
Assumption   id, category, key, value_numeric, value_text, unit,
             default_value, description, affects
RateBand     id, role, low, high, currency
```

Seeded from the tables above. Editable through the interface. Reset restores the seed.
`RateBand` has no `default_value` column in this model — a changed rate stays changed until
edited back by hand; only `Assumption` rows are affected by "reset to defaults."
