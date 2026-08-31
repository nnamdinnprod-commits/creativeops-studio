# Product Specification — CreativeOps Studio V1

## The problem

A traditional in-house studio runs on this chain:

> brief → producer → spreadsheet → email → creative team → review → more email → deadline problem

Information about capacity, risk and creative performance lives in different heads and
different tools. The producer spends their day reconstructing state instead of making
decisions.

## The proposed chain

> brief → AI brief analysis → production-ready brief → priority → capacity check →
> resource recommendation → production → creative intelligence → recommended next action →
> **human approval** → production / localisation → delivery

The point is not to remove the producer. It is to give the producer better information and
more time for the decisions only a human should make.

## Core principle

AI should improve creative work and decision-making, not simply make production cheaper.
AI structures, flags, and recommends. Humans approve. Approval is visible in the data
model, not just in the UI copy.

## The single most important thing the demo must show

One unbroken thread from a performance insight to a scheduled piece of work:

> creative insight → production recommendation → capacity check → named resource →
> localisation requirement → human approval → project in the pipeline

If a reviewer only understands one thing, it should be this. Every other screen supports it.

---

## Screen 1 — Operations Dashboard

The landing view. Answers "what needs attention?" before the user asks.

**Must show**

- Counts: active projects, on track, at risk, blocked
- Deadlines in the next 7 days
- Team capacity summary (aggregate utilisation, count of overloaded people)
- Localisation progress across active projects
- A prioritised "Needs attention" panel

**The attention panel** is AI-generated from a deterministic snapshot. Each item names the
project, states the cause, and links to the screen where it can be resolved. Example shape:

> **3 projects need intervention this week**
> - *Campaign X* is at risk — Alex is at 95% allocation against a Friday deadline → *Resources*
> - *Campaign Y* is blocked — German localisation review unassigned → *Localisation*
> - *Campaign Z* cannot safely enter production — brief readiness 58% → *Brief Assistant*

Each line must be traceable to real state in the database. The AI writes the prose; Python
computes which projects qualify. Never let the model invent the list.

## Screen 2 — Creative Pipeline

Kanban board. Columns:

`Brief → Ready → Assigned → In Production → Creative Review → Waiting on Client → Approved
→ Delivered`, plus three exception-state columns at the end (`On Hold`, `Cancelled`,
`Archived`) — not points on the sequence, always reachable regardless of readiness.
REVIEW_02.md P5.4 split `Waiting on Client` out of what Creative Review used to conflate:
"we are reviewing" and "they are sitting on it" are different situations, and only one of
them is a problem this studio caused. A hold, a cancel, or a move to an earlier stage
captures a reason, shown on the card.

**Card shows:** project name, brand, market, priority, owner, deadline, risk flag,
localisation indicator, production tempo (when fast-track).

**Interactions:** move a project between columns, change priority, change tempo, open
detail, filter by brand / market / status / risk.

Movement between columns is a button or select, not drag-and-drop, in V1, and is free —
any column to any column, not only the next one forward — because a market re-version,
copy swap, resize, or artwork resend can legitimately skip straight to Creative Review or
Delivered. What's actually gated is readiness: a status change that would violate the
readiness rule (e.g. moving an incomplete brief into In Production) prompts a warning
naming what's missing — this is the operational logic a reviewer will look for. The gate
is scoped by `production_tempo` (`fast_track` / `standard` / `full_production`) —
fast-track work skips it entirely; REVIEW_02.md P5.3.

**Project detail view** shows brief text, extracted brief fields, deliverables,
assignments, localisation rows, risk assessment, and the recommendation history for that
project.

## Screen 3 — Resource & Capacity Planning

The screen that proves operational credibility. Give it the most care.

**Table:** person, role, contracted capacity %, allocated %, available %, status
(Available / Tight / Overloaded), current assignments, next deadline. Only Team (internal)
and currently-engaged Talent Pool members appear here — REVIEW_02.md P5.5: "Team — always
on the roster, always counted. Talent pool — not on the capacity roster until engaged." An
engaged pool member shows an External badge and their engagement's end date.

**Talent pool** — every external person not currently engaged, with role, skills, day rate
range and lead time (`docs/ASSUMPTIONS.md`'s `RateBand`), and an Engage action (project,
dates, allocation) that routes through the same mechanism Timeline and Localisation use.
The lead time is enforced, not just displayed: an engagement can't start before it, and is
refused outright if that leaves no runway before the work is due.

**Conflict detection** is deterministic: a person is Overloaded when allocated exceeds
capacity, Tight above a configurable threshold (default 85%). Conflicts are listed with
the specific projects and dates causing them.

**AI recommendation** on a conflict, for example:

> Move Campaign X from Alex to Maya.
> Alex drops from 95% to 80%, protecting the Friday deadline.
> Maya has 28% available and holds the required skill (motion).

The recommendation is stored, shown with **Accept** and **Reject** buttons, and only
changes assignments when accepted. Rejected recommendations stay visible in history.

The arithmetic in the recommendation is computed in Python and passed to the model. The
model phrases it. It must never be the source of the numbers.

## Screen 4 — AI Brief Assistant

A textarea where the user pastes a messy real-world request.

**Extracts:** objective, audience, markets, channels, deliverables, formats, deadline,
dependencies, resource needs, localisation requirements.

**Produces a Brief Readiness Score** (0–100) with the rubric visible — the score must be
explainable, not a black box. Show which required fields are present, which are missing,
and what each missing field blocks.

> **72% — Needs clarification**
> Missing: final asset specifications, confirmed audience, approval owner, localisation deadline.
> Without asset specs, production time cannot be estimated and the Friday date is unverifiable.

**Then:** `Create project from brief` writes a project into the pipeline at status Brief,
pre-populated with everything extracted, with unresolved gaps recorded as open questions.

A brief below a threshold (default 70%) creates the project but cannot move past Ready
until gaps are filled. This is the "identifying missing information" competence made
mechanical.

## Screen 5 — Creative Intelligence

Mock performance data only. Clearly labelled.

**Shows:** creative variants with market, format, CTR, engagement rate, conversion rate,
spend, and a comparison view (e.g. lifestyle-led vs product-only by market).

**Derives an insight:**

> Lifestyle-led creative is outperforming product-only creative in Germany
> (CTR 2.4% vs 1.1% across 6 variants).

**Translates it into a production recommendation:**

> **Recommended action** — produce 3 additional lifestyle-led variants for Germany
> **Estimated effort** — 2 working days
> **Suggested resource** — Maya, 28% available Thursday–Friday
> **Localisation** — German copy review required
> **Status** — Awaiting approval

Accepting creates a project in the pipeline with the assignment and localisation rows
already attached. This closes the loop described at the top of this document.

---

## Localisation model

Lightweight. Not a translation platform.

Each project has a source market and target markets. Each target market has a row with
language, status, assigned translator/vendor, review status and QA status.

Status ladder: `Not started → In translation → In review → QA → Approved`

Risk rule: a target market whose deadline is within N days with no assigned translator, or
stalled in review, flags the parent project at risk and surfaces on the dashboard.

## Cross-cutting UI requirements

- Disclaimer footer on every screen (see `docs/POSITIONING.md`)
- Empty, loading and error states for every AI-backed panel
- Every AI-generated block visually marked as AI-generated
- Every pending recommendation shows Accept / Reject
- Readable at laptop width; mobile is not a V1 requirement

## Success criteria

A Creative Operations leader viewing the demo should conclude the builder understands
creative operations, understands resource and production constraints, understands where AI
genuinely helps, is not trying to replace creative judgement, and can turn an operational
problem into working software.

V1 is not optimised for feature count. It is optimised for demonstrating judgement.
