# Planning and Scheduling

**Status: specification for session 2. Not built in V1.**

## Why this exists

Planning is the largest part of a producer's job. A creative operations tool without a
schedule view is missing the thing producers actually live in — and the schedule is what
gets shared with stakeholders, what travel gets booked against, and what decisions get
timed around.

It also fixes the ordering error in V1. Right now the app goes brief → capacity → assign,
which treats allocations as given. The correct order is:

> brief → **schedule** → capacity → assign

A person is 95% allocated *because of scheduled phases*, not because a seed file said so.
Once allocations derive from a schedule, the capacity numbers stop being assertions and
start being consequences.

## Governing rule, unchanged

Dates are computed in deterministic Python. The model explains feasibility and consequence;
it never produces a date. Same rule as `AI_WORKFLOWS.md`, applied here.

---

## Project types and phase templates

A project has a **type**. Each type carries a template of phases with default durations,
dependencies, and the roles each phase needs. Templates are editable — every studio's
differ, and a hardcoded one is a claim rather than a tool.

Phase fields: `name`, `default_days`, `kind` (`prep` / `production` / `review` /
`delivery`), `required_roles`, `is_milestone`, `is_client_review`, `scales_with_volume`.

Milestones are zero-duration markers at phase boundaries. They are where meetings go.

### Film / branded content

| Phase | Days | Kind | Notes |
|---|---|---|---|
| Brief & scoping | 2 | prep | |
| Pre-production | 8 | prep | treatment, casting, locations, permits |
| **PPM** | 0 | milestone | pre-production meeting — client sign-off on approach |
| Shoot | 2 | production | scales with volume |
| Offline edit | 5 | production | |
| Client review 1 | 3 | review | |
| Revisions | 2 | production | |
| VFX & grade | 3 | production | |
| Audio mix | 2 | production | |
| **Final approval** | 3 | review | milestone at end |
| Delivery & versioning | 2 | delivery | scales with volume |

### Event

| Phase | Days | Kind | Notes |
|---|---|---|---|
| Brief & scoping | 2 | prep | |
| Concept & design | 5 | prep | |
| **Fabrication cutoff** | 0 | milestone | hard gate — build cannot start before design lock |
| Fabrication & build | 15 | production | longest lead time; usually the binding constraint |
| **Running order meeting** | 0 | milestone | |
| Rehearsal | 1 | production | |
| Live | 1 | production | fixed date — see "anchored phases" below |
| Wrap & asset delivery | 3 | delivery | |

### Stills

| Phase | Days | Kind |
|---|---|---|
| Brief & scoping | 1 | prep |
| Pre-production | 4 | prep |
| Shoot | 1 | production |
| Selects & client review | 3 | review |
| Retouching | 4 | production |
| Client review | 2 | review |
| Delivery & resizing | 2 | delivery |

### Social / AI-generated content

| Phase | Days | Kind |
|---|---|---|
| Brief & scoping | 1 | prep |
| Concept & scripting | 2 | prep |
| Generation & production | 3 | production |
| Client review | 2 | review |
| Revisions | 1 | production |
| Localisation handoff | 1 | delivery |
| Delivery | 1 | delivery |

Localisation phases from `PRODUCT_SPEC.md` attach after `Localisation handoff` for any
project with target markets, one track per market, running in parallel.

---

## Back-scheduling

**Input:** project type, delivery date, optional volume factor.
**Output:** a dated phase for every row in the template.

Algorithm:

1. Start at the delivery date and walk the template **in reverse**.
2. Each phase ends one working day before the next phase begins.
3. Count working days only — skip weekends. A configurable holiday list is out of scope.
4. Phases marked `scales_with_volume` multiply their duration by the volume factor
   (6 assets = 1.0; 30 assets ≈ 2.5; the curve is in `ASSUMPTIONS.md`, and is deliberately
   sub-linear because setup cost is fixed).
5. Milestones take the date of the phase boundary they sit on.
6. Client review windows come from `ASSUMPTIONS.md`, not from the template, so a studio can
   change its review policy in one place.

**Anchored phases.** Some phases have immovable dates — an event's live day, a shoot booked
against talent availability. An anchored phase pins to its date and the schedule computes
outward in both directions from it. If back-scheduling from delivery conflicts with an
anchor, report the conflict rather than silently moving the anchor.

**When the computed start is in the past**, say so plainly and quantify it:

> Working backwards from 14 November, this project needed to start 6 November — 4 working
> days ago. Options: compress client review from 3 days to 2 (recovers 2 days), drop the
> revisions phase (recovers 2 days), or move delivery to 18 November.

Never silently compress. The producer decides what gives.

**Compression order**, when the user asks for options, in the order the system should
suggest them: reduce review windows to their minimum, then reduce revision phases, then
overlap phases that don't strictly depend on each other, then flag that the date is not
achievable. Never compress a fabrication lead time or an anchored phase — those are
physical constraints, not policy.

---

## Timeline view

Projects down the left, weeks across the top, phase bars between.

- One row per project; click to expand into per-phase rows
- Bars coloured by phase `kind`, not by project — the eye should read *what stage* across
  the portfolio at a glance
- Milestones as diamonds on the bar
- A vertical "today" line
- Filter by brand, market, type, owner
- A phase bar is outlined as a conflict when a role it requires has no person with capacity
  in that window

**Do not use a month-grid calendar.** It cannot show a three-week phase or a dependency,
which is most of what matters here. **Do not import a Gantt library** — configuration will
eat the session. A hand-built bar timeline in HTML and CSS reads better and costs a
fraction of the time.

Milestone meetings surface as a list beside the timeline: what meeting, which project, which
date, derived from the schedule. That list is the practical output a producer takes away.

---

## Data model additions

```
ProjectType      id, name, description
PhaseTemplate    id, project_type_id, sequence, name, default_days, kind,
                 required_roles, is_milestone, is_client_review, scales_with_volume
ProjectPhase     id, project_id, name, kind, start_date, end_date,
                 is_milestone, is_anchored, status, assigned_person_id (nullable)
```

`Project` gains `project_type_id` and `volume_factor`.

**Assignments derive from phases.** When a schedule is generated, each production phase
requiring a role creates a candidate assignment for that window. This is the change that
makes capacity real — and it means the capacity service in `app/services/capacity.py` needs
no rewrite, only a different source of assignment rows.

---

## What the AI does here

One function, added to `AI_WORKFLOWS.md`:

`assess_schedule_feasibility(computed_schedule_facts) -> ScheduleAssessment`

```json
{
  "feasible": false,
  "shortfall_days": 4,
  "binding_constraint": "fabrication lead time",
  "statement": "The build cannot start until design locks on 12 November, which leaves 11 working days against a 15-day fabrication requirement.",
  "options": [
    {"action": "move_delivery", "detail": "to 18 November", "recovers_days": 4},
    {"action": "compress_review", "detail": "client review 3 days to 2", "recovers_days": 1}
  ],
  "confidence": "high",
  "caveats": []
}
```

Every date and every day-count in that payload is computed before the prompt is built. The
model chooses which constraint to name as binding and writes the sentence.

---

## Out of scope

Resource levelling algorithms. Critical path calculation. Drag-to-reschedule. Holiday
calendars. Multi-project dependency chains. Baseline-versus-actual tracking.

Each is a real thing a production tool eventually needs. None belongs in the session that
first makes a schedule appear on screen.
