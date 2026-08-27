# Owner Review — Round 1

Review of the working V1 by the project owner, a Creative Operations professional, turned
into a prioritised change list.

Claude Code: work this list in order. Everything under **Session A** before anything under
**Session B**.

---

## Session A — small fixes

Four changes, roughly an hour. None require new tables.

### A1. Fix the team capacity tile

**Problem:** the dashboard shows "aggregate utilisation 49%", which averages the problem
away. One person at 95% and one at 15% average to something that reads as comfortable while
a deadline is about to be missed.

**Change:** lead with the distribution, demote the average.

> **2 of 8 over capacity · 1 tight · 5 available**
> Team aggregate 49%

The counts link to the Resources screen. Same computation, `app/services/capacity.py`, no
new logic — a presentation change with a real point behind it.

### A2. Build a Localisation screen

**Problem:** "2 of 20 localisation rows approved" is accurate and useless. It doesn't say
which languages, which projects, or where the queue is stuck.

**Change:** a screen at `/localisation` showing:

- A grid: projects down, target markets across, each cell showing its stage, colour-coded on
  the `not_started → in_translation → in_review → qa → approved` ladder
- A per-market summary: volume in flight, who is assigned, oldest item, any market with an
  unassigned translator and a due date inside the risk window
- Filter by market and by stage

The dashboard tile becomes a link to it, and its text changes to name the bottleneck rather
than count rows: *"German queue clear · French review unassigned, 4 days to deadline."*

### A3. Deadline items in Needs Attention, and typed items

**Problem:** an approaching deadline with work unstarted is an attention item and doesn't
appear as one. And the item causes aren't distinguishable at a glance.

**Change:**

- Add a deadline rule to the attention snapshot: a project whose deadline falls within 7
  working days and whose status is behind where the schedule implies it should be.
- Every attention item carries a visible type tag — `capacity` · `deadline` · `brief` ·
  `localisation` — with a consistent colour, and links to the screen where it gets resolved.

The AI still writes the prose; Python still decides which projects qualify. The invention
guard in `AI_WORKFLOWS.md` still applies.

### A4. One recommendation per conflict

**Problem:** requesting a recommendation twice for the same conflict produces two identical
pending recommendations to click through.

**Change:** requesting a recommendation for a conflict that already has a `pending` one
replaces it rather than appending. Accepted and rejected recommendations stay in history
untouched — that history is the audit trail and must not be collapsed.

If the underlying facts have not changed, say so rather than silently re-running the model:
*"Existing recommendation still current — the conflict is unchanged since it was generated."*

---

## Session B — planning, in this order

**Complete** as of 2026-08-27 — all seven steps below are built; see `DECISIONS.md` 016–023
for what each one actually landed and the judgment calls made along the way. `PLANNING.md`
carries an inline "Built" marker on every section this touched.

Read `PLANNING.md` first. Build in this sequence; each step is independently demonstrable,
so a short session still lands something.

1. **`ProjectType` and `PhaseTemplate`** with the four seeded templates. No UI yet.
2. **The back-scheduling service** — deterministic, unit-tested. Tests before UI: this is
   the same rule as `capacity.py` in Phase 3, and for the same reason.
3. **Schedule generation on a project**, producing `ProjectPhase` rows.
4. **The timeline view** — projects down, weeks across, phase bars, milestone diamonds,
   today line.
5. **Assignments derived from phases**, so capacity figures follow from the schedule rather
   than from seed data.
6. **`assess_schedule_feasibility`** wired into the timeline and dashboard.
7. **Milestone meeting list** beside the timeline.

If time runs out, stop after 4. A visible timeline with correct dates carries the argument
even without derived assignments.

---

## Session C — estimation, if there is a third session

**Complete** as of 2026-08-27, see `DECISIONS.md` 025–026.

Read `BRIEF_MODES.md` and `ASSUMPTIONS.md`.

1. `Assumption` and `RateBand` tables, seeded, with the editable table screen — **done**
2. Quick Estimate mode with assumption controls and recomputation — **done**
3. Indicative costing from the rate bands — **done**
4. `single_best_question` surfaced prominently — it is the most useful thing on that screen — **done**

---

## Deferred, deliberately

**Production intelligence** — unions, right-to-work, filming permissions and business
affairs by market. The owner is right that this is where the concept goes and right that it
would make the tool genuinely valuable. It is out of scope for the prototype because any
version buildable now would be invented or stale, and incorrect regulatory guidance in a
portfolio piece circulating among industry people is worse than an absent feature.

`ASSUMPTIONS.md` carries the safe version and the words to use when presenting it.

**Not changing:** the Pipeline screen. The owner reviewed it and found nothing to fix. Leave
it alone.

---

## Housekeeping for Claude Code

When starting Session B:

1. Add `PLANNING.md`, `BRIEF_MODES.md`, `ASSUMPTIONS.md` and this file to the document table
   in `CLAUDE.md`.
2. Add the new entities from `PLANNING.md` to `DATA_MODEL.md` — do not duplicate the spec,
   reference it.
3. Add `assess_schedule_feasibility` and `quick_estimate` to `AI_WORKFLOWS.md`, including
   their mocks. The app must still run with no API key.
4. Log each of these in `DECISIONS.md` as they land.

Every non-negotiable in `CLAUDE.md` still applies, and the readiness-gate refusal
(`check_readiness_gate` / `validate_transition` in `app/routes/pipeline.py`) must still pass
after these changes — `BRIEF_MODES.md` explicitly preserves it, and
`tests/test_pipeline_transitions.py` covers it (added 2026-08-27, see `docs/DECISIONS.md`
015).
