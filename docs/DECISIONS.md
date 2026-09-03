# Decision Log

Append-only. One entry per architectural decision, new dependency, or change to a documented
rule. Newest at the bottom.

Keep entries short. The value is the *why* — a future reader (including a future Claude Code
session) needs to know what the alternative was and why it lost.

Template:

```
## NNN — Title
Date:
Decision:
Alternatives considered:
Why:
Consequences:
```

---

## 001 — Single-process stack for V1
Date: pre-build (set in CLAUDE.md)
Decision: One Python process serving both API and HTML. No separate frontend dev server.
Alternatives considered: FastAPI + React/Vite (two processes); Next.js full-stack.
Why: The build has a one-day budget and the builder is new to this tooling. A split
frontend/backend costs setup time and CORS debugging that buys nothing a reviewer will see.
Next.js remains the fallback if a public deployed URL becomes a requirement.
Consequences: No client-side routing. Interactivity via HTMX and Alpine. Deployment is
simple but the frontend is less impressive as a standalone artefact.

## 002 — Numbers are computed in Python, never by the model
Date: pre-build (set in AI_WORKFLOWS.md)
Decision: All arithmetic — utilisation, readiness scores, availability, metric comparisons —
is deterministic Python. The model receives computed facts and produces prose and choices.
Alternatives considered: letting the model reason over raw data and return figures.
Why: Reproducible demos, unit-testable logic, and an honest answer to "what if it
hallucinates?" — the wording can vary, the numbers cannot.
Consequences: More Python service code up front. Prompts are longer because facts are passed
in explicitly. Worth it.

## 003 — Recommendations are persisted, not ephemeral
Date: pre-build (set in DATA_MODEL.md)
Decision: A `Recommendation` table holds every AI suggestion with pending/accepted/rejected
state, the rationale, and the computed facts it was based on.
Alternatives considered: generating suggestions on the fly and applying them directly.
Why: "AI recommends, humans decide" is the product's central claim. Persisted state with an
audit trail makes it structurally true rather than a UI label.
Consequences: One extra table and an accept/reject handler per recommendation kind. Also
gives the demo a history view, which strengthens the argument.

## 004 — Phase 1 architecture proposal approved
Date: 2026-08-21
Decision: Approved as proposed — Option A stack; folder structure with `services/capacity.py`
and `services/ai/` as the two enforcement points for the non-negotiables; 7 SQLAlchemy models
matching DATA_MODEL.md exactly; route list covering all 5 screens plus recommendation
accept/reject and localisation actions; template inventory with shared `_ai_badge`,
`_ai_panel_loading`, `_ai_panel_error` partials; 5 AI functions per AI_WORKFLOWS.md.
Alternatives considered: none — Option A was already the documented default, no deviation
proposed.
Why: Nothing in the docs required a different approach; the proposal was a direct
translation of PRODUCT_SPEC.md, DATA_MODEL.md and AI_WORKFLOWS.md into a build order.
Consequences: Proceeding straight to Phase 2 (Skeleton).

## 005 — Implementation-level dependencies added
Date: 2026-08-21
Decision: Added `uvicorn` (runs the app — CLAUDE.md names FastAPI but not its server),
`python-multipart` (FastAPI requires it to parse HTML form POSTs, which every mutating route
uses), `pydantic-settings` and `python-dotenv` (the "one settings object reading from
environment" rule needs a settings library, not hand-rolled `os.environ` parsing).
Alternatives considered: hand-rolled env parsing instead of pydantic-settings.
Why: These are not stack choices, just what FastAPI + the settings rule require to run at
all. Hand-rolling env parsing would violate "no literal config values scattered in code"
just as easily as it would satisfy it.
Consequences: None beyond four extra lines in requirements.txt.

## 006 — Added "Working with the owner" rule to CLAUDE.md
Date: 2026-08-21
Decision: Before each significant step, state in plain language what is about to happen and
why; after each step, state what changed and what can be checked in the browser; flag any
approval that contradicts the docs before acting on it.
Alternatives considered: none — owner-requested addition.
Why: The owner is a Creative Operations professional, not an engineer, and wants intent and
consequence explained, not syntax — and wants to be told, not silently overridden, if an
approval conflicts with what the docs say.
Consequences: Narration becomes part of the working method, not optional colour.

## 007 — requirements.txt uses minimum versions, not exact pins
Date: 2026-08-21
Decision: Changed `requirements.txt` from `==` exact pins to `>=` minimums.
Alternatives considered: keeping exact pins; installing an older Python via Homebrew instead.
Why: This machine's only Python 3.11+ interpreter is 3.14 (the system `/usr/bin/python3` is
3.9, too old for the stack). The exact versions originally pinned predate Python 3.14 and
have no pre-built package for it, so pip tried to compile `pydantic-core` from Rust source
and failed — the build toolchain didn't support 3.14 either. Letting pip resolve current
versions picked up releases that do ship 3.14 wheels, which installed cleanly. Installing an
older Python was the other option but is a bigger, less reversible change to the machine for
a one-day build.
Consequences: No exact version pins for this project — a `pip freeze` after install would
give a reproducible lockfile if that's ever wanted, but isn't needed for a single-day,
single-machine build.

## 008 — Added openai and anthropic SDKs for live AI calls
Date: 2026-08-21
Decision: Added `openai` and `anthropic` to requirements.txt, imported only in
`app/services/ai/client.py` per the rule that no other file imports a provider SDK.
Alternatives considered: skipping live-provider support and shipping mock-only.
Why: AI_WORKFLOWS.md requires `AI_PROVIDER` to support `openai` / `anthropic` / `mock`, and
Phase 4's exit criteria asks that `analyse_brief` work against a live provider if a key is
set. Both installed cleanly on this machine's Python 3.14 environment.
Consequences: Two more dependencies; untested against a live key in this session since none
was provided — the app still runs and is fully tested in mock mode regardless.

## 009 — Localisation risk rule built in Phase 4, not Phase 5
Date: 2026-08-21
Decision: Wrote `app/services/localisation_risk.py` (the deterministic at-risk rule) during
Phase 4 instead of waiting for Phase 5, and used it to feed the Phase 4 dashboard attention
panel.
Alternatives considered: leaving the dashboard's localisation-caused attention item out until
Phase 5.
Why: PRODUCT_SPEC.md's own example attention panel includes a localisation-blocked item, and
BUILD_PLAN.md already named this exact file in the Phase 1 folder structure — it wasn't new
scope, just built slightly earlier than scheduled because Phase 4 genuinely needed it.
Consequences: Phase 5 reuses this function rather than duplicating it; Phase 5's own scope
shrinks to wiring it onto pipeline cards and the localisation status ladder.

## 010 — Seed brief text adjusted; noted a cross-doc scoring inconsistency
Date: 2026-08-21
Decision: Added "DE" to the seeded vague-brief project's text so the rubric scores it at
exactly 50%, and left DEMO_DATA.md's stated "55–70 band" target unmet rather than forcing it.
Alternatives considered: tuning the extraction heuristic or rubric weights until the score
landed in 55–70.
Why: AI_WORKFLOWS.md's rubric weights make 55–70 mathematically unreachable for a brief
missing exactly the four fields DEMO_DATA.md names as gaps (format specs, audience, approval
owner, deadline) — those four sum to exactly 50 of the 100 points, so the ceiling is 50%, not
55-70. This is an inconsistency between the two docs, not something fixable in code without
either contradicting the published rubric or inventing facts the brief text doesn't contain.
Consequences: The seeded vague brief now scores 50% — still well below the 70% threshold, so
it demonstrates the readiness-gate behavior correctly. Owner has been told; docs not silently
edited to match.

## 011 — Centralised Jinja2Templates into app/templates_env.py
Date: 2026-08-21
Decision: Replaced five separate `Jinja2Templates(directory="app/templates")` instances (one
per route file) with a single shared instance, with `settings` registered as a Jinja global.
Alternatives considered: passing `settings` into every individual TemplateResponse call.
Why: AI_WORKFLOWS.md requires a mode indicator ("mock"/"openai"/"anthropic") in the footer on
every screen. A per-file template instance meant a Jinja global set on one didn't reach the
others; centralizing was the only way to guarantee it everywhere without repeating it in six
route handlers.
Consequences: One shared template environment for the whole app — also means any future
global (e.g. current user) only needs to be added once.

## 012 — Project.risk_level stays unpopulated; risk badges computed live
Date: 2026-08-21
Decision: Pipeline card and project-detail risk indicators are computed on every request from
current Assignment/Localisation state (via app/services/attention.py's snapshot), not read
from or written to the `Project.risk_level` / `risk_reason` columns DATA_MODEL.md defines.
Alternatives considered: recomputing and writing `risk_level` on every relevant mutation
(assignment change, localisation update, status change) so the stored column stays accurate.
Why: A stored-and-synced value needs update hooks on every mutation path that could affect
it, which is real complexity for a one-day build with no benefit a live computation doesn't
already provide — risk state changes the moment underlying data changes either way, and nothing
reads risk_level except the UI, which can just compute it fresh each time.
Consequences: The `risk_level`/`risk_reason` columns exist in the schema but are always their
default (none/null). If a future need requires reading risk state without recomputing
(e.g. an API consumer, a background report), populating the columns properly would need
revisiting.

## 013 — Added a live public deployment on Render, reseeding on every boot
Date: 2026-08-21
Decision: Added `render.yaml` for a free-tier Render web service, with the start command
running `python -m app.seed` before `uvicorn` on every boot.
Alternatives considered: a persistent disk with a periodic reset job; leaving the live demo
un-deployed (BUILD_PLAN.md's original "second session" scope).
Why: The owner explicitly asked for a working, publicly reachable demo, not just screenshots.
A public demo is a shared, mutable database — any visitor can accept/reject recommendations
or move pipeline cards. Render's free tier has no persistent disk by default, so the SQLite
file is wiped on every redeploy and on every wake from its ~15-minute inactivity sleep;
reseeding at boot turns that into a feature — the demo self-heals to a clean state instead of
staying polluted for the next visitor — rather than fighting it with a paid persistent disk.
Consequences: State any one visitor changes (an accepted recommendation, a moved card) can
disappear the next time the service sleeps and wakes. That's the intended tradeoff for a
public, unauthenticated demo, not a bug — documented in the README.

## 014 — V2 Session A: the four owner-reviewed fixes from FEEDBACK_LOG.md
Date: 2026-08-26
Decision: Implemented A1–A4 from `creativeops-docs-v2/FEEDBACK_LOG.md`.
- **A1**: Dashboard's capacity tile leads with the distribution ("N of M over capacity ·
  tight · available") instead of the aggregate %, which was averaging real problems away.
- **A2**: New `/localisation` screen — project × market grid, colour-coded by stage, with a
  per-market summary (volume in flight, translators, oldest item, risk flagged first). New
  `summarize_by_market()` in `localisation_risk.py`, reusing the existing risk check.
- **A3**: Attention causes renamed to four canonical tags (`capacity`/`deadline`/`brief`/
  `localisation`), shown consistently on Dashboard and Pipeline. Added a deadline rule: a
  project within 7 working days of deadline still in an early stage (Brief/Ready/Assigned) is
  flagged — an honest interim proxy for FEEDBACK_LOG.md's schedule-derived wording, since the
  Session B schedule system doesn't exist yet.
- **A4**: Re-requesting a recommendation for a conflict with a pending one only replaces it
  if the underlying facts changed (exact equality on `computed_facts_json`); otherwise
  nothing regenerates.
Alternatives considered (A3): waiting for Session B before adding any deadline rule at all.
Why: the four items were independently scoped and shippable now; the schedule-derived version
can replace the proxy later without changing the attention-panel contract.
Bug found and fixed while testing A4, not one of the four items: `resources.py`'s
candidate-building had no role filter — with no skill match it fell back to whoever had
spare capacity with no role check, and recommended reassigning a design project to Jonas, an
external translator. Same class of bug as an earlier fix, on a code path that had never been
exercised. Excluded `producer` and `translator` roles from reallocation candidates.
Consequences: none of this was pushed or deployed until the owner asked why the live demo
still showed the old behaviour — a reminder to say explicitly when work is local-only.

## 015 — Resolved two dangling references found before starting Session B
Date: 2026-08-27
Decision: (1) Moved `creativeops-docs-v2/{PLANNING,BRIEF_MODES,ASSUMPTIONS,FEEDBACK_LOG}.md`
into `docs/` and added them to CLAUDE.md's doc table, ahead of schedule, since the directory
was sitting uncommitted on disk. (2) `BRIEF_MODES.md` and `FEEDBACK_LOG.md` both referenced a
`SUPERVISION.md` "check 4" that doesn't exist anywhere in the repo or its history. Owner
confirmed the intended referent is the readiness-gate refusal (`check_readiness_gate`/
`validate_transition` in `app/routes/pipeline.py`); both docs reworded to point at that code
directly.
Alternatives considered: writing a new `SUPERVISION.md` to match the reference; leaving it
flagged to revisit before Session B.
Why: the owner picked the option that resolves the ambiguity now rather than deferring it.
Consequences: resolving this surfaced a real gap — `check_readiness_gate`/`validate_transition`
had no automated test, despite BUILD_PLAN.md's Phase 3 exit criteria requiring "an invalid
transition is refused with a reason." Closed immediately: added
`tests/test_pipeline_transitions.py` covering skip-forward refusal, allowed forward-by-one,
backward-always-allowed, the readiness threshold, and the ungated no-brief-analysis case.

## 016 — Session B step 1: ProjectType and PhaseTemplate models, seeded from PLANNING.md
Date: 2026-08-27
Decision: Added `ProjectType`/`PhaseTemplate` models and a `PhaseKind` enum (`prep`/
`production`/`review`/`delivery`), plus `seed_phase_templates()` seeding the four templates
from PLANNING.md (Film 11 phases, Event 8, Stills 7, Social 7; 33 rows). Models-and-seed-data
only, per FEEDBACK_LOG.md's own step ordering — no UI, no `Project.project_type_id` yet.
Alternatives considered: leaving `required_roles` blank until Session B needs it; asking the
owner to specify roles per phase before writing seed data.
Why, two judgment calls PLANNING.md's phase tables don't settle:
1. **`required_roles` per phase** — inferred from each phase's name/notes against the
   existing `PersonRole` enum, which has no director/DP/fabricator roles; "producer" stands
   in for externally-vendor-coordinated work like shoot crews and fabrication. A placeholder,
   not a studio judgement call the way ASSUMPTIONS.md's rate bands are — flag for review once
   Session B step 5 uses these roles for real.
2. **Three rows list "milestone" as their `Kind`**, not one of PLANNING.md's four `PhaseKind`
   values. Reclassified each to the real kind at whose boundary it sits (PPM → review;
   Fabrication cutoff → prep; Running order meeting → production) with `is_milestone=True`,
   `default_days=0`. `Final approval` keeps `is_milestone=False` despite a "milestone at end"
   note, since it also has 3 days of duration — the schema has one flag per row, not a
   separate "milestone at boundary" concept.
Consequences: `required_roles` values are an unreviewed inference — nothing else reads these
tables yet, so getting them wrong has no live-app consequence today, but flag before step 5.

## 017 — Owner review round 2: more approval checkpoints, budget sign-off, editability confirmed
Date: 2026-08-27
Decision: Updated all four phase templates in `seed.py`/`PLANNING.md` (43 phase rows, up from
33):
- **Film**: added `Pre-PPM` before `PPM`; added `Budget sign-off` after `PPM`; added a second
  client review (`Client review 2`) after `Revisions`.
- **Event**: `is_client_review=True` on every phase except `Fabrication & build` and `Live`;
  added `Budget sign-off` after `Concept & design`.
- **Stills**: added a `PPM` milestone after `Pre-production`; added `Budget sign-off` right
  after it.
- **Social**: added `Brief approval`, `Concept approval`, `Budget sign-off`, and a final
  `Final approval` after `Revisions`.
- Confirmed two capabilities as documented requirements, not yet built: phase day counts
  become editable once a schedule exists; producers can insert ad-hoc phase rows a template
  doesn't anticipate.
Alternatives considered: building a minimal edit screen now, ahead of step 4 (the timeline
view). Also reversed same-session: `Budget sign-off` and `Pre-PPM` were first drafted
internal-only — owner corrected this immediately, both are client-facing.
Why: the owner chose to document the editability requirement now and build it once there's
an actual schedule to edit against.
Consequences: "a week before" (Pre-PPM's timing) isn't yet an encoded day gap — no
back-scheduling logic exists yet (step 2) to consume it. All added milestone rows are 0 days,
so template totals only changed for Film (32→35 working days); Event/Stills/Social totals
unchanged since their additions were all 0-day milestones.

## 018 — Session B step 2: back-scheduling service
Date: 2026-08-27
Decision: Added `app/services/scheduling.py`'s `back_schedule()` — a pure function taking a
project type's `PhaseTemplate` rows, a delivery date, and an optional volume factor,
returning dated phases. No `ProjectPhase` model or route touches this yet (step 3 persists
its output).
Alternatives considered: computing review-phase durations from each template row's own
`default_days`; deferring anchored-phase handling vs. noting it explicitly out of scope.
Why, three implementation choices:
1. **Client-review-duration phases use a fixed `CLIENT_REVIEW_DAYS = 3` constant, not the
   template's stored `default_days`** — PLANNING.md's point 6 ("client review windows come
   from ASSUMPTIONS.md, not the template") taken literally, as a stand-in until that editable
   table exists (Session C). Real, visible effect: Stills'/Social's `Client review` rows are
   seeded at `default_days=2`, but scheduled duration is 3 — confirmed with the owner against
   a rendered schedule.
2. **Anchored phases are out of scope for this step.** PLANNING.md describes them (an event's
   Live day, a shoot pinned to talent availability) as part of the algorithm, but anchoring
   is a per-project-instance fact that belongs on `ProjectPhase.is_anchored`, which doesn't
   exist until step 3.
3. **Feasibility is data, not prose.** `back_schedule()` returns `is_feasible` and
   `shortfall_working_days` only — narrating it in a sentence is `assess_schedule_feasibility`'s
   job (step 6), not this service's, per the standing rule that Python computes and the model
   explains.
Consequences: a past-start scenario is reported without altering any computed date — "never
silently compress" holds structurally, since this function has no compression logic at all;
that arrives with step 6's options list.

## 019 — Session B step 3: schedule generation, ProjectPhase persisted
Date: 2026-08-27
Decision: Added `ProjectPhase` and a `ProjectPhaseStatus` enum (`not_started`/`in_progress`/
`complete`) per PLANNING.md's data model additions. `Project` gained `project_type_id`
(nullable FK) and `volume_factor` (default 1.0). Added `generate_schedule(db, project)`,
which runs `back_schedule()` and persists the result as `ProjectPhase` rows, replacing any
existing rows for that project. No route or screen touches this yet (step 4 is where a
schedule first becomes visible).
Alternatives considered: inferring `ProjectPhaseStatus`'s values vs. asking the owner; a bulk
`Query.delete()` for replacing a project's old schedule vs. per-row ORM deletes.
Why:
1. **`ProjectPhaseStatus` values aren't specified anywhere** — inferred to match the shape
   `Deliverable`/`Localisation` already use. Low-stakes, easily revisited since nothing reads
   this field yet.
2. **The "replace, don't duplicate" delete used `Query.delete()` first, and that was a real
   bug**: SQLite reuses rowids after a bulk delete, and `Query.delete()` doesn't remove the
   deleted objects from SQLAlchemy's identity map, so regenerating a schedule raised an
   identity-map warning when new rows landed on the same primary keys. Fixed by querying
   existing rows and calling `db.delete()` on each.
Consequences: local dev's `creativeops.db` needed a full reset (`create_all()` doesn't
`ALTER` existing tables) — Render's reseed-on-boot picks up the new schema automatically.
`Project.project_type_id` stays unset for all existing projects; nothing in the Brief
Assistant's create-project flow sets it yet.

## 020 — Session B step 4: the timeline view
Date: 2026-08-27
Decision: Added `/timeline` and a new positioning-math module, `app/services/timeline.py`,
scoped to exactly what FEEDBACK_LOG.md's step 4 names: projects down the left, weeks across
the top, phase bars coloured by `kind`, milestones as diamonds, a today line. Filters mirror
the existing Pipeline/Localisation pattern. Per-project rows collapse by default and expand
into a per-phase table. A hand-built CSS bar chart, not a Gantt library, per PLANNING.md's
explicit instruction.
Deliberately not built here, since they depend on state that doesn't exist yet:
conflict-outlined bars (no assignments exist until step 5), the milestone meeting list (step
7 by name), and any on-screen feasibility messaging (step 6's job).
Alternatives considered: inventing new demo projects to populate the screen vs. giving three
of the existing twelve a `project_type_id`.
Why: DEMO_DATA.md fixes the seed at 12 projects, so three existing ones were typed instead,
screened against two rules: never touch the two projects carrying DEMO_DATA.md's required
capacity-overload/reassignment conflict or their deadlines; prefer a spread of feasibility
outcomes over uniformly comfortable ones, since an infeasible schedule is the honest scenario
PLANNING.md's back-scheduling section describes, not a bug to hide. Final picks (checked
against each template's working-day need): Mother's Day Static Set → Social (comfortably
feasible), Spring Lookbook → Stills (mildly short), Autumn Prints FR Push → Film (badly
short, exercises the largest template).
Consequences: three of the twelve demo projects now carry a schedule; nothing about their
status, deadline, assignments, or localisation changed, so DEMO_DATA.md's five required
conflicts are intact. No browser automation was available this session — the rendered HTML
was inspected directly instead of a real visual check, flagged explicitly rather than
claimed.

## 021 — Session B step 5: assignments derive from phases
Date: 2026-08-27
Decision: Added `app/services/assignment.py` (`phase_candidates()`, `assign_phase()`,
`unassign_phase()`) and wired an Assign/Unassign control into `/timeline`'s expand view.
`ProjectPhase` gained `required_roles` (copied from the source template); `Assignment`
gained a nullable `project_phase_id`, so a reassignment can find and replace exactly the row
it produced. `capacity.py` was not touched — confirmed a phase assignment shows up on
`/resources` unmodified, matching PLANNING.md's promise for this step.
Alternatives considered: auto-picking a person deterministically inside `generate_schedule()`;
a phase-derived assignment at 100% allocation; checking a candidate's capacity only at the
phase's start date.
Why, three real decisions:
1. **A human still clicks Assign — nothing auto-picks a person.** Given CLAUDE.md's "AI
   recommends, humans decide" and this codebase's existing candidate-then-click pattern,
   auto-picking felt like the wrong default even for deterministic logic.
2. **The allocation default started at 100%, and that was a real problem**: checked against
   the seeded roster (mostly 20–55% allocated already), 100% required returned zero
   candidates for most production phases. Lowered to 50% — verified 6 of 9 production phases
   across the three demo schedules then found at least one candidate.
3. **`assign_phase()` refuses milestones and non-`production`-kind phases outright** (a
   milestone is a 0-duration meeting, not assignable work), and refuses a role mismatch — the
   same rule decision 014 fixed for the resource-reallocation candidate list.
4. **Capacity is checked across the phase's full date window**, not just its start date, via
   `capacity.py`'s existing `allocation_timeline()` — more correct here since production
   phases commonly span several days.
Consequences: a producer can still assign someone already tight elsewhere by overriding past
what `phase_candidates()` offers — `capacity.py`'s existing conflict detection catches it on
the Resources screen exactly as it would any other overload, the intended integration at the
time (later reconsidered in decision 032).

## 022 — Session B step 6: assess_schedule_feasibility, the first Session B AI function
Date: 2026-08-27
Decision: Added `app/services/ai/feasibility.py` (`assess_schedule_feasibility`) — the sixth
AI function, following the existing five's plumbing. Its deterministic facts come from a new
`build_feasibility_facts()` in `scheduling.py`, not the AI layer. Wired into `/timeline` (a
red "Behind" badge plus a statement-and-options panel) and `/dashboard` (a "Schedule" tile) —
only called for a project whose schedule doesn't fit its deadline.
Alternatives considered: letting the model choose `shortfall_days`/`options` itself;
computing `binding_constraint` deterministically instead of letting the model pick from
candidates; attempting the third compression priority (overlapping non-dependent phases).
Why, three real decisions:
1. **Every number is recomputed from the facts after parsing, never trusted from the
   response** — `feasible`, `shortfall_days`, and `options` are overwritten unconditionally.
   `binding_constraint` is the one field left to the model, per PLANNING.md's explicit
   instruction, and even then is validated against the given candidates and corrected if the
   model names anything else.
2. **`binding_constraint_candidates` are Python's top 3 non-milestone phases by working-day
   count**, giving the model a real bounded choice, consistent with how `recommend_resource`
   already works.
3. **The third compression priority (phase overlap) is not attempted** — it needs a phase
   dependency graph this data model doesn't have, so it's left out rather than guessed at.
   "Flag not achievable" is what the panel already does when no option closes the gap.
Consequences: `move_delivery`'s recovered days always exactly close the shortfall;
`compress_review` and `drop_revisions` may recover less, and nothing sums or combines them —
the panel lists independent moves for a producer to weigh, not a solved plan. Verified
against real seed data: both infeasible demo projects from decision 020 now show a real
computed shortfall and options.

## 023 — Session B step 7: milestone meeting list, Session B complete
Date: 2026-08-27
Decision: Added `milestone_list()` to `timeline.py` — a pure function over the same
already-filtered phase data the route builds for the bar chart, so the meeting list respects
whatever filter is active. Sorted chronologically. Rendered as a sidebar card on `/timeline`,
restructuring the page into a two-column layout. This was the last step in Session B's
sequence.
Alternatives considered: dropping past milestones from the list entirely; querying fresh from
the database instead of reusing the route's already-filtered data.
Why:
1. **Past milestones stay in the list, visually muted, not dropped** — a milestone that
   should already have happened is real information, especially alongside step 6's "Behind"
   badge.
2. **`milestone_list()` takes the already-loaded, already-filtered phase data**, the same
   shape as `build_timeline()` in the same file — one filter pass now drives both the chart
   and the list, so they can never disagree about scope.
Consequences: PLANNING.md's one remaining unbuilt Timeline item is the conflict-outline rule
(a phase bar outlined when its required role has no one with capacity) — step 5 built the
assignment data this would read, but nothing consumes it yet, a real open gap worth closing
separately from Session B's now-complete step list.

## 024 — Conflict-outline rule closed: PLANNING.md's Timeline view now fully built
Date: 2026-08-27
Decision: Added `conflicted_phase_ids()` to `timeline.py` — takes the route's
already-computed `candidates_by_phase_id` (from `phase_candidates()`, step 5) and returns
phase ids with an empty candidate list. Wired into `/timeline` as a red ring on any
unassigned production phase's bar with no one who could take it on, visible without
expanding the row.
Alternatives considered: also checking assigned phases for whether their assignee has since
become overloaded elsewhere; querying the database fresh instead of reusing the route's
already-computed dict.
Why:
1. **Only unassigned phases are checked.** PLANNING.md's wording is "a role it requires has
   no person with capacity" — a staffing-gap fact, not an overload fact. Once assigned,
   whether that person is now stretched thin is a different, already-covered question
   (`capacity.py`'s conflict detection). Conflating the two would make this rule redundant
   and flicker on unrelated assignments elsewhere.
2. **`conflicted_phase_ids()` takes the dict, not the database** — the route already builds
   it for the assign-picker; recomputing separately would double the query cost and risk the
   two checks disagreeing.
Consequences: closes the last open item from PLANNING.md's Timeline view section. Verified
against real seed data: 3 phase bars across the three demo schedules are flagged, all in
roles the roster is thin on (motion design).

## 025 — Session C step 1: Assumption and RateBand tables, editable screen
Date: 2026-08-27
Decision: Added `Assumption` and `RateBand` models, `seed_assumptions()` (21 `Assumption`
rows across ASSUMPTIONS.md's four categories, 6 `RateBand` rows, one per `PersonRole`),
`app/services/assumptions.py` (`get_value`, `get_rate_band`, `reset_all`), and
`/assumptions` — a grouped, inline-editable table plus reset-to-defaults, following the same
thin-route/deterministic-service/template pattern as every other screen.
Alternatives considered: wiring `scheduling.py`'s hardcoded `CLIENT_REVIEW_DAYS`/
`VOLUME_SCALE_BANDS` constants to read live from this table in the same step; modeling
"Confidence bands" as a dedicated two-column table instead of flattened `Assumption` rows.
Why:
1. **Not wiring Session B's constants to this table yet, deliberately.** ASSUMPTIONS.md's
   "changing a value recomputes any open estimate immediately" has no "open estimate" yet to
   recompute — that's Quick Estimate mode (step 2), the real payoff moment. Retrofitting
   already-tested Session B code in the same step that introduces the tables would bundle two
   kinds of change with no visible demo moment to justify the risk.
2. **"Confidence bands" flattened to one `Assumption` row per number**, matching
   ASSUMPTIONS.md's own schema (one `value_numeric` per row) rather than inventing a second
   table the doc doesn't ask for.
3. **`RateBand` has no reset-to-defaults behaviour** — ASSUMPTIONS.md's own `RateBand`
   columns have no `default_value` field, unlike `Assumption`. Followed the doc's data model
   rather than adding an unspecified column.
Consequences: editing a value on `/assumptions` today only changes that stored number — the
screen is real and functional but inert until step 2 reads from it.

## 026 — Session C steps 2–4: Quick Estimate mode, Session C complete
Date: 2026-08-27
Decision: Built Quick Estimate mode in full — steps 2 (duration), 3 (costing), and 4 (the
`single_best_question` callout) landed together, since they're naturally the same screen and
the same deterministic pass over phase templates. Added the 7th AI function, `quick_estimate`
(reads raw text and infers the request's shape, closer in kind to `analyse_brief` than the
facts-narrating functions); `app/services/estimate.py`'s `compute_estimate()` (deterministic
duration/cost/earliest-delivery, reading `Assumption`/`RateBand` live — step 1's real payoff);
`/brief` now defaults to Quick Estimate, Full Brief moved behind `?mode=full` (its
routes/logic otherwise untouched). Recompute is pure Python — editing asset count,
photography toggle, review rounds, or confidence never calls the model again; state
round-trips via hidden form fields, not a new table.
Alternatives considered: building steps 2–4 as three separate commits; scaling volume only
for `PhaseTemplate` rows flagged `scales_with_volume`; persisting QuickEstimate results in a
new table.
Why, two real decisions and one bug caught before shipping:
1. **A real, pre-existing gap surfaced immediately**: only Film's phases carry
   `scales_with_volume=True` (decision 016) — Event, Stills, Social have none, so asset count
   did nothing for "social," BRIEF_MODES.md's own primary example. Fixed by giving Quick
   Estimate its own coarser rule: every production-kind phase scales, not only flagged rows —
   a deliberate divergence from `back_schedule()`'s precise per-phase flag, documented in both
   places.
2. **Costing compounds two sources of range**: each cost line's low/high comes from that
   role's `RateBand` range, and the confidence factor then widens the already-ranged sum
   further — duration has no rate-band range to start from, so its low/high is just the
   confidence factor on one number. A real interpretive choice, documented explicitly since
   BRIEF_MODES.md's formula could read either way.
3. **No persistence** — BRIEF_MODES.md only says an estimate "can be saved for reference,"
   not that it must be; a new history table felt like avoidable scope for a first pass.
Consequences: Session C (all 4 steps) complete. ASSUMPTIONS.md's one remaining honest gap:
`scheduling.py` still reads its own hardcoded constants, not this table — noted there
explicitly, not silently left inconsistent.

## 027 — Wire app/services/scheduling.py to read live Assumption values
Date: 2026-08-27
Decision: `back_schedule()` and `build_feasibility_facts()` now take `client_review_days`/
`client_review_minimum_days` as parameters (defaulting to the existing hardcoded constants,
kept as fallbacks for callers with no `Assumption` table — mainly tests). `generate_schedule()`
fetches `client_review_days` live via `assumptions.py`; `/dashboard` and `/timeline` do the
same for `client_review_minimum_days`. `volume_factor_for()` gained an equivalent optional
override for consistency, though nothing calls it live yet.
Alternatives considered: giving `back_schedule()` a `db: Session` parameter directly instead
of threading the resolved value through as an argument; wiring `volume_factor_for()` to a
live caller in this same change.
Why:
1. **`back_schedule()` stays a pure function, no `db` parameter** — its whole design
   (decision 018) was deliberately DB-free and directly testable; threading a resolved value
   through as a parameter gets the live value in without breaking that contract.
2. **`volume_factor_for()` was not wired to a live caller** — checked first that
   `generate_schedule()` never calls it (it passes `Project.volume_factor` straight through,
   a stored field, not derived from asset count anywhere in this path). Wiring a function
   with no real caller to live data would have been theatre.
3. **Two real bugs caught by testing against the actual seed path, not just fixtures**:
   `seed.py`'s `main()` called `seed_demo_schedules()` before `seed_assumptions()` — a fresh
   `--reset` would have crashed, since `client_review_days` wouldn't exist yet; fixed by
   reordering. And `/dashboard`/`/timeline` fetched `client_review_minimum_days`
   unconditionally, which would crash on a database with no `Assumption` rows and no
   scheduled projects; fixed by gating the fetch behind "is there a scheduled project."
Consequences: `generate_schedule()` (and any route or seed step that calls it) now
hard-depends on the `Assumption` table being seeded first — existing tests updated
accordingly.

## 028 — Ran the full demo end to end; rewrote DEMO_SCRIPT.md to match
Date: 2026-08-27
Decision: Executed DEMO_SCRIPT.md's entire 8-step walkthrough against a real running process
from a cold reset, driving every click via HTTP rather than trusting the script's claims.
Every refusal message, computed number, and outcome matched except two, both caused by real
product changes made after the script was written, not app bugs. Rewrote the script to match
and added a 9th step (Timeline and planning) covering Sessions B and C, which had no demo
coverage at all.
Alternatives considered: leaving the stale numbers with a footnote; making the new step
optional rather than part of the numbered flow; hardcoding its exact dates/figures the way
earlier steps do.
Why, two real discrepancies and one design choice:
1. **Dashboard's "2 projects need intervention" is now 4** — decision 014's deadline rule
   (added after this script was written) flags two more. The script now says "4" honestly
   but keeps the walkthrough focused on the original two.
2. **A recommendation step's named person changed** — not a bug: the mock correctly reads
   live capacity, and an earlier step's accepted reassignment had already shifted the numbers
   by the time this step runs. Fixed the quoted example and added a note explaining why, so a
   future change isn't mistaken for a bug again.
3. **The new step deliberately doesn't quote exact dates or day-counts** the way earlier
   steps sometimes do, since its content depends on elapsed working days since the seed ran —
   describing the pattern instead of the number keeps the script from going stale.
Consequences: DEMO_SCRIPT.md now covers all 9 screens, not 6. Run time grew from ~6.2 to ~7.3
minutes with the new step, retitled honestly and marked as the first thing to cut if time is
short.

## 029 — REVIEW_02.md P0: revoke real brand names, replace with checked-clean invented ones
Date: 2026-08-31
Decision: Reversed POSITIONING.md's clause permitting "publicly known consumer brand names as
fictional tenants" — the clause the real brand names traced back to. Replaced the real names
everywhere in the product surface with invented ones, each checked against a web search for
real-company collisions before use.
Alternatives considered: using the review's own suggested replacement set and alternates as
given; rewriting git history to remove historical blobs still containing the old names.
Why, two real findings that changed the plan:
1. **Every single name the review proposed collided with a real, active company** in the
   same or an adjacent industry — checked by search, not assumed clean. A short
   invented-sounding word very often already belongs to some small, real business (likely
   because corporate registries hold near-exhaustive dormant-name inventories), so perfect
   zero-hit assurance isn't achievable for a word this short. The standard actually applied:
   no same-or-adjacent-industry collision and no substantial exact-name company — matching
   the review's real concern (a reviewer recognising the name), not a literal zero anywhere.
   Final mapping: **Nordelva Group** (parent) → **Fotomera** (NL), **Halveth** (DE),
   **Cassenvale** (FR/ES).
2. **Git history was left alone, deliberately, not overlooked.** A deep audit found
   historical blobs still containing the old names. Rewriting published history is exactly
   the hard-to-reverse, shared-state action this project's operating rules require checking
   with the owner before attempting — surfaced as a separate decision rather than acted on
   unilaterally.
Consequences: `tools/audit.py`'s expected-brands constant updated to the actual final names.
Verified clean via full-repo grep, the test suite, a fresh seed, and the audit tool against a
local instance — not yet re-verified against the live deployment or pushed, a separate
explicit step given the site is public.

## 030 — REVIEW_02.md P1: two demo-schedule deadlines were the actual bug, not literal dates
Date: 2026-08-31
Decision: Widened two seeded project deadlines (Spring Lookbook, Autumn Prints FR Push) to
bring their schedules within a plausible feasibility range — one now fully feasible, the
other exactly 2 working days behind, inside the review's "no more than 2" bar.
Alternatives considered: auditing every date in `seed.py` for hardcoding, the literal fix
REVIEW_02.md's text describes; dropping Film from the demo-scheduled set entirely so every
schedule is comfortably feasible.
Why:
1. **Every date in `seed.py` was already a relative offset** — the "29 working days behind"
   symptom had nothing to do with hardcoded dates; it was decision 020's deliberate pairing
   of a short seeded deadline with the largest template, which is badly infeasible on every
   reseed forever, not a one-time drift. The owner's direct testing overruled that earlier
   call.
2. **Kept a small, real shortfall instead of making everything feasible** — dropping Film
   entirely would have silently broken DEMO_SCRIPT.md's step 8, which narrates a real
   "Behind" badge and feasibility panel. A plausible shortfall is the honest fix; "29 working
   days" was never plausible, but zero isn't the alternative to implausible.
3. **Both changes are safe** — every `Assignment` and `Localisation` row uses its own
   independent date offset, never derived from `Project.deadline`, so neither change is
   load-bearing for DEMO_DATA.md's five required conflicts.
Consequences: the wider spread also helps REVIEW_02.md's "deadlines spread across six weeks"
bar. `Deliverable`/`Localisation` rows tied to these two projects now show due dates earlier
than the project's new deadline — left as is, since a deliverable due ahead of overall
delivery is normal.

## 031 — REVIEW_02.md P7 copy item, done early: renamed "Mother's Day Static Set"
Date: 2026-08-31
Decision: Renamed the seeded project to "Yearly Mother's Day Assets" (project name, comment,
and dict key in `seed.py`). The `campaign` field and `brief_raw` text are unchanged.
Why: the owner asked directly whether this project's schedule was tied to the real Mother's
Day — REVIEW_02.md's own flagged item. Confirmed: the deadline is a relative offset from
"today," so it never lands near the actual holiday (March UK, May elsewhere in Europe) on any
given reseed. Moving the date can't fix this — no fixed offset from "today" reliably lands
near a specific calendar holiday — so renaming, framing the project as ongoing/evergreen
seasonal-asset production, is the only fix that holds under a stale-never demo reseed.
Consequences: taken out of P7 order, ahead of P2–P6, since it was a direct question about
live app behaviour rather than a request to work the review section by section. The rename
touches display text only, not scheduling math — reconfirmed unaffected.

## 032 — REVIEW_02.md P2: one definition of "how loaded is this person," enforced not just displayed
Date: 2026-08-31
Decision: Four changes to `capacity.py` and its callers:
1. Added `peak_allocation_pct(assignments, from_date)` — the worst allocation across a
   person's timeline from a date onward, not a single-date snapshot. `person_capacity()` (and
   everything built on it — the Resources table, dashboard over-capacity count, Creative
   Intelligence) now uses this instead of a snapshot that only looked at exactly one day.
2. Consolidated a window-bounded peak calculation `assignment.py` had reimplemented locally
   into `capacity.py`'s `max_allocation_pct()`. Added `available_pct()` and
   `aggregate_utilisation_pct()` so trivial arithmetic isn't re-derived at each call site.
   Deleted the now-unused snapshot function.
3. **`assign_phase()` now enforces the same availability rule `phase_candidates()` uses to
   populate its own dropdown**, instead of allowing a direct call to bypass it. *(Source doc
   referenced "decision 020" here; corrected to 021, which is where this override design and
   its "conflict detection catches it elsewhere" reasoning actually appear.)* That assumption
   doesn't hold — nothing ever re-checked availability after the first assignment, so
   repeated or replayed assigns could stack a person's allocation with no ceiling. This,
   combined with the snapshot-only figure fixed in change 1, is the actual mechanism behind
   REVIEW_02.md's reported "540% against 80% contracted."
4. Labelled the accepted-recommendation figures on `/resources` "At time of recommendation" —
   correctly frozen at generation time, but nothing signalled they weren't live, which is how
   they read as one more contradictory number.
Alternatives considered: leaving the override in place and instead capping `allocation_pct`
at display time — rejected, since it would hide a real data problem behind a fake number, the
opposite of what P1 already established.
Why: REVIEW_02.md's fix item 1 ("one place, route through capacity.py") was already mostly
true — the actual bug was semantic, not structural: two call sites used the same primitive
with different window definitions (a single date vs. a full timeline), so they could
legitimately disagree about the same person on the same day.
Consequences: a person free today but double-booked starting next week now shows as
tight/overloaded immediately, not only once that week arrives — a real behaviour change, and
the correct trade for this app (DEMO_DATA.md's conflicts are meant to be visible, not
deferred). Verified: the "1 of 8" over-capacity reading became "1 of 6" with no
contradiction; two remaining audit-tool flags on `/timeline`/`/intelligence` are confirmed
false positives (a differently-scoped metric, and a regex matching the tail of a long
decimal), left for a P7 copy pass.

## 033 — Rounded float-arithmetic seed values on Creative Intelligence
Date: 2026-08-31
Decision: `seed.py`'s DE `CreativeInsight` rows computed `engagement_rate`/`conversion_rate`
via unrounded float arithmetic, occasionally landing on values like `1.5499999999999998` from
ordinary binary float imprecision, rendered raw in `/intelligence`'s table. Wrapped both in
`round(x, 2)` at the point of computation.
Why fixed at the source rather than in the template: `insight.py`'s own aggregate computation
already rounds correctly — only the seed data feeding the raw table was unrounded, and
nothing else writes a `CreativeInsight` row in V1 scope.
Consequences: none beyond cleaner numbers — no test asserted the old unrounded values.
Noticed as a side effect of the audit tool flagging what looked like a "9999%" capacity bug on
`/intelligence`, actually this unrelated float-formatting issue.

## 034 — REVIEW_02.md P3: write-through and recompute
Date: 2026-08-31
Decision: Investigated each of five reported symptoms directly (a repro script per symptom
against the actual routes) before changing anything — most of the codebase already computes
at display time with no caching, so the fix was four specific gaps plus one symptom that
didn't reproduce.
1. **"Accepting a resource recommendation doesn't update capacity elsewhere"** — the
   Assignment row and capacity recompute correctly; the real bug is
   `ProjectPhase.assigned_person_id`, a denormalized field `assign_phase()` sets for Timeline
   display, which the reallocation handler never touched for a phase-derived assignment.
   Fixed: `computed_facts_json` now carries the exact `assignment_id` (needed because a
   person can hold more than one Assignment on the same project), and the matching
   `ProjectPhase.assigned_person_id` updates in the same transaction.
2. **"Changing an Assumption doesn't reschedule affected projects"** — real, but narrow:
   `client_review_days` is the only assumption `generate_schedule()` persists into stored
   phases; everything else is already read live at display time. Fixed by regenerating the
   schedule for every project with one, only when that specific key changes (regenerating for
   an unrelated assumption would destroy manual phase assignments for nothing). This surfaced
   a second, previously latent bug: no cascade existed between `ProjectPhase` and
   `Assignment`, so regenerating orphaned any Assignment against a deleted phase — fixed by
   deleting those rows in the same transaction as the phases they belonged to.
3. **"Assigning a translator on the localisation page does nothing"** — literally true, the
   page had no assign control at all. Added an inline assign form per grid cell, with an
   optional `return_to` field (validated against a known prefix, never an arbitrary posted
   URL) so the action redirects back to wherever it was submitted from.
4. **"Assigning a resource on the project page does nothing"** — also literally true. Added a
   manual whole-project assign route, with the same eligibility and spare-capacity rules as a
   phase assign, replacing rather than stacking a second row for the same person/project pair.
5. **"Pipeline status changes don't update the dashboard"** — did not reproduce; every
   dashboard figure is already recomputed fresh on each load. Noted here so a future session
   doesn't re-investigate the same claim from scratch.
6. **"Everything appears unassigned after actions that should have assigned it"** — the same
   `ProjectPhase.assigned_person_id` staleness fixed in item 1.
Deliberately not fixed here: a translator's "allocation" — this data model has no Assignment
row for a translator at all, and REVIEW_02.md's P5.5 explicitly scopes an external talent
pool with lead time/cost as its own item.
Consequences: every fix verified both by a targeted regression test and against a real
running server (reassignment syncing its phase, a live assumption edit changing a stored
phase duration, a translator assign updating the market summary and risk flag live, a manual
assign changing a live allocation figure).

## 035 — REVIEW_02.md P4: insight lifecycle state, without a new stored status column
Date: 2026-08-31
Decision: Extended the existing "one pending recommendation per conflict" rule to Creative
Intelligence, giving each market's insight the four-state lifecycle the review asks for
(`new`/`recommendation_pending`/`actioned`/`dismissed`) — but stored almost none of it. Added
one column, `CreativeInsight.dismissed_reason`. Everything else is computed at display time in
`compute_insight_status()`: `recommendation_pending`/`actioned` are derived from whether a
pending or accepted Recommendation exists for that market; only `dismissed` has no
Recommendation to derive from, so it's the one thing needing real storage.
`/intelligence/recommend` mirrors the existing dedup pattern (replace a pending recommendation
only if facts changed); blocks outright only for the two terminal states. New dismiss endpoint
(a required reason) sets `dismissed_reason` across every row in that market's group, since
dismissal is a property of the market-level opportunity, not one raw row.
Alternatives considered: an explicit `InsightStatus` enum column storing all three derivable
states; a separate `Opportunity`/`InsightGroup` table for the market-level concept.
Why: REVIEW_02.md's own P3 rule, applied one section later — nothing derived may be stored
where it can drift. A dedicated grouping table was rejected as more schema than this demo's
scale needs.
Consequences: rejecting a pending recommendation reverts the insight to `new` — the review's
four states don't include a distinct "rejected" state. Verified end to end: repeated requests
for the same market created one Recommendation; accepting showed "Actioned" and removed the
request control; dismissing one market left others untouched.

## 036 — REVIEW_02.md P5.1: one shared project-reference partial
Date: 2026-08-31
Decision: Added `_project_ref.html`, a single Jinja macro rendering the
`<a href="/projects/{id}">{name}</a>` pattern every project link in the app already used ad
hoc. Applied it at all 14 occurrences the survey found across every template that names a
project, including the 6 already correctly linked (for consistency) and the 8 that weren't
linked at all.
Three of the 8 needed more than swapping in the macro:
1. **Dashboard's Schedule card** nested the project link inside the card's own outer link —
   invalid, unpredictable HTML. Restructured the card as a div with its own per-alert links.
2. **Timeline's row header** was the text inside an accordion toggle `<button>` — same
   nested-interactive-element problem. Split the disclosure arrow from the project name,
   which is now a real link (previously clicking the name only toggled the row and went
   nowhere).
3. **Resources' "Current assignments" column** had no project id in scope at all — the route
   pre-flattened assignments into a joined string before the template saw them. Changed it to
   pass project ids instead, letting the template look names back up.
Alternatives considered: a Jinja custom filter or Python global instead of a macro file —
rejected since an explicit macro import keeps a template's dependencies visible in its own
header, matching how the Python code already prefers explicit imports over ambient globals.
Consequences: a recommendation-outcome note was deliberately left without its own link, since
the card immediately above it already links the same project. Two remaining audit-tool flags
(`/brief`, `/intelligence`) were confirmed by hand to be crawl-state artifacts, not real gaps
— both only show a project link once something real exists to link to.

## 037 — REVIEW_02.md P5.2: Timeline shows every project it safely can
Date: 2026-08-31
Decision: `/timeline`'s route already showed every project with a generated schedule — the
"3 of 16" gap was entirely that only 3 of 12 seeded projects had ever been given a
`project_type_id` (decision 021's own scope limit). Extended the demo-scheduled set from 3 to
6, covering every seeded project at status Ready through Creative Review, and added "Planned"
styling to distinguish Ready-status (planned) from committed work.
Considered and rejected extending to all 10 non-Brief projects:
1. **Two projects with deliberately tight, narratively load-bearing deadlines stay
   excluded** — one drives DEMO_DATA.md's capacity-overload conflict, the other sits inside
   the dashboard's deadline-proximity window narrated in DEMO_SCRIPT.md. Widening one of
   their deadlines to fix its schedule shortfall was tried and reverted, since it silently
   pushed the project outside the attention window instead — an honest tradeoff, not a bug to
   hide, but not worth trading one review requirement for another.
2. **Two functionally-finished projects stay excluded** — a backward schedule computed
   against a deadline already passed or nearly so produces a large, meaningless "behind
   schedule" number for work nobody is still staffing.
3. **Two still-at-Brief projects stay excluded**, since the review's own instruction is
   "from Ready onwards."
For the three added, two deadlines were widened slightly to bring their shortfalls under the
audit tool's plausibility ceiling, checked first against DEMO_SCRIPT.md/DEMO_DATA.md to
confirm neither is narratively load-bearing.
Consequences: the seed's console output now reports the actual project count instead of a
hardcoded string. Verified: all added projects' feasibility shortfalls are within the
plausibility ceiling; the audit tool's P5.2 and P1 checks both pass.

## 038 — REVIEW_02.md P5.3: sequence is free, the readiness gate is scoped by tempo
Date: 2026-08-31
Decision: `validate_transition()` no longer refuses a forward skip — any status to any status
is allowed (only "already in this status" is refused). `check_readiness_gate()` is unchanged
in what it checks, but is now skipped entirely when a new `production_tempo` field
(`fast_track`/`standard`/`full_production`, default `standard`) is `fast_track`. Added a
tempo route and pipeline-card badge. Also enriched the gate's refusal message to name the
actual missing fields, not just the aggregate readiness score.
Why: `standard` and `full_production` get identical gate behaviour — the review only
describes fast-track behaving differently, and inventing an undescribed distinction between
the other two tiers felt like the wrong kind of judgement call to make silently. No seeded
project's tempo was set away from the default, since none is actually a fast-track case in
its brief content — relabelling one that isn't would be less honest than leaving it accurate;
the new tempo control makes the feature demonstrable live instead.
Consequences: the test asserting sequential-only movement was inverted to assert free
movement instead. Verified against a running server: a status can now skip stages in one
call, and setting a project fast-track visibly skips the gate.

## 039 — REVIEW_02.md P5.4: four new lifecycle states, scoped narrowly
Date: 2026-08-31
Decision: Added `waiting_on_client`, `on_hold`, `cancelled`, `archived` to `ProjectStatus`,
plus `Project.status_reason` (the most recent reason given, not a full history).
`waiting_on_client` sits in the main pipeline sequence right after Creative Review; the other
three are exception states appended after Delivered. `check_readiness_gate()` exempts all
three exception states outright (pausing or cancelling must always be possible), but
`waiting_on_client` stays fully gated, since reaching it means production already started.
Dashboard's active-project count now excludes the three exception states but still counts
`waiting_on_client` as active. A status-change form field captures a required reason for a
move to hold/cancelled or backward on the sequence.
Deliberately not built here: the review's own P6.3 heading ("derive the Blocked tile from
these states") — checked first that nothing already mis-triages `waiting_on_client` as a
capacity problem (it doesn't; that positive surfacing is P6.3's job). No seeded project's
status was changed to any of the four new values, since none of the 12 is actually in one of
these states in its brief content — the new board control makes each state demonstrable live
instead.
Consequences: all 11 pipeline columns render; a hold with a reason persists and displays; the
dashboard still renders correctly with the new states present.

## 040 — REVIEW_02.md P5.5: external resource is a Talent Pool, not a permanent roster row
Date: 2026-08-31
Decision: Reused the existing `Person.is_external` flag rather than inventing a new entity —
Team and Talent Pool are different queries over the same table, not different tables. Three
changes:
1. **`capacity.py`'s roster functions now exclude an unengaged external person** via
   `is_actively_engaged()` — internal people always pass; an external person passes only
   during a window an actual Assignment covers. This is the literal fix for externals sitting
   on `/resources` at a permanent, meaningless 0%.
2. **`RateBand` gained `lead_time_days`** per role, editable alongside the existing rate
   range.
3. **One engagement mechanism, three screens**: new `engage_person()` creates or replaces the
   Assignment row for any engagement, enforcing the spare-capacity rule and, for an external
   person, a lead-time floor via `earliest_feasible_start()`. Phase assign, project-page
   manual assign, and a rewritten translator assign all route through it now.
Alternatives considered: refusing an engagement outright whenever the requested start is
earlier than the lead time allows.
Why: tried first, and it would have made translator-assign nearly unusable for near-term due
dates. Redesigned so the engagement's start auto-adjusts to the earliest genuinely feasible
date, and that adjusted window — not the requested one — is what's checked against the work's
own deadline. Refusing only when there's truly no runway left is the meaningful signal ("this
can't be done in time"), not "you asked for the wrong date." Re-checked against the
deliberate FR bottleneck row: it lands exactly on the earliest feasible date — an honest
"only just possible" result, not a false refusal or a free pass.
Also considered and rejected: extending the AI-recommendation candidate list to include
external pool members now — that's explicitly P5.6's job, which this decision's mechanism
exists to serve, not pre-empt.
Consequences: a new "Talent pool" section on `/resources` lists every unengaged external
person with rate, skills, and earliest feasible start; the main capacity table marks an
engaged external "External" with an end date. Verified: the over-capacity count dropped from
"1 of 8" to "1 of 6," the expected consequence of the roster fix, not a regression.

## 041 — REVIEW_02.md P5.6: resource recommendations return ranked options
Date: 2026-08-31
Decision: `recommend_resource` now returns a list of options (reassign / engage_external /
move_delivery, each with its own action, cost, and dates) plus a recommended label,
replacing the old single-action shape. Every option is computed by Python before the AI call,
and the AI wrapper overwrites the result from those facts after parsing — the model's only
real input is which option to recommend and the rationale prose. This also closes a
pre-existing gap: unlike `assess_schedule_feasibility`, the old function never re-derived its
impact figures from facts after the call, despite AI_WORKFLOWS.md already describing that
discipline as the rule. `move_delivery`'s "days needed" is computed as how many days the
transfer assignment's own start would need to move to clear the actual overlap causing the
conflict, not a schedule simulation this app has no model for.
Added an external motion-designer candidate to the seed roster, since the review's own
illustrative example ("Engage Lars, external, motion") could never otherwise appear.
Two real bugs found only by testing this live, worth recording precisely because nothing in
the existing suite would have caught either:
1. A mock's rationale text built eagerly from a dict literal crashed on a reassign-only
   recommendation, trying to string-parse an "Engage " clause that was never present.
   Rewritten as an if/elif chain that only builds the rationale actually needed.
2. A candidate's "available from" date was computed as "the day after their nearest unrelated
   commitment ends" — wrong, since a person with enough headroom is available for the whole
   window regardless of an unrelated, survivable commitment elsewhere. This silently excluded
   the built-in reassignment candidate from her own conflict's options. Fixed to
   `max(earliest_feasible_start, window_start)`, the only thing that actually gates a start
   date. The same root cause also mispriced the `engage_external` option on the full original
   window length rather than the shorter engageable stretch, and separately meant accepting
   `engage_external` applied the original assignment's dates rather than the lead-time-
   adjusted window just shown — all three fixed together by giving every option its own
   explicit start/end dates, used identically for the displayed detail, the cost math, and
   what's applied on accept.
Consequences: the hand-built-payload tests predating this decision couldn't have caught any
of the three bugs, since they bypass the real computation path entirely — a new test module
exercises the real pipeline end to end specifically because of this, with a named regression
test per bug. An existing test helper now requires an `assignment` argument, since every real
recommendation has one.

## 042 — REVIEW_02.md P6.1 + P6.2: positive-loop visibility, Creative Intelligence shrunk
Date: 2026-08-31
Decision: Two sections done together since they touched the same accept-flow code.
**P6.1** — every "say so" claim is re-verified against the same live check the dashboard
itself uses, never assumed from having taken an action: a translator assign only says "Risk
cleared" if the row was actually at risk before and isn't after (a row never at risk gets a
plain confirmation instead — claiming a cleared risk that wasn't one would be the same kind
of invented positive news CLAUDE.md forbids for negative numbers); a resource reallocation
only leads with "Risk cleared" if the person is actually no longer conflicted, since they can
still be conflicted by a different overlap the accept didn't touch. New "Recently resolved"
dashboard panel, sourced from data every accept path already wrote — the one panel that shows
a user they made something better, since every other panel leads with a problem.
**P6.2** — checked first whether the mock varies by input before assuming a single canned
response: it does vary by market/CTR/sample size, but never reads the brand the form asks the
user to pick — a real, related bug, not the one the review suspected. Fixed: added a
minimum-sample-size gate so a comparison on too thin a sample is now tagged "not significant"
rather than silently dropped or shown as a real finding; added a real reporting-period
selector (one option today, since seed data has only one period, but the mechanism is
genuine); and closed the one part of the review's decision-rule check that didn't already
hold — an accepted Creative Intelligence recommendation now gets a real generated schedule
and appears on the Timeline, not just the pipeline.
Consequences: verified end to end — the full bottleneck-to-resolution loop, the significance
split on a fresh reseed, the reporting-period label, and the full accept-to-schedule-to-
Timeline chain for a Creative Intelligence recommendation.

## 043 — REVIEW_02.md P6.3: derive the Blocked tile from the four named states
Date: 2026-08-31
Decision: New `build_blocked_snapshot()`, deliberately separate from the existing at-risk
snapshot — "at risk" answers a deadline-exposure question, "blocked" answers "what is
structurally stuck and why," and the review names four sources that don't map onto the
existing cause set. A project can be both. Each source, and the honest gap it required
filling:
1. **`waiting_on_client` beyond the agreed review window** — "since when" has no dedicated
   status-history table, so `Project.updated_at` is used as a fair proxy, since nothing else
   writes to a project row between status changes.
2. **Brief below readiness threshold, past its intended start date** — no `intended_start`
   field exists; `deadline − estimated_days` is the honest proxy, computed from fields the
   row already carries rather than inventing a new one.
3. **Localisation stalled with no translator** — deliberately not gated by the existing risk
   window (a different, standing question: stuck regardless of days remaining, not "is the
   deadline close").
4. **A started phase with nobody assigned** — milestones and phases with no required roles
   are excluded, since those can never be staffed in the first place.
The Blocked dashboard tile links to a filtered pipeline view sourced from the same function
it counts, so the two numbers can't disagree; board cards gained a distinct "Blocked" badge
that takes precedence over an at-risk badge on the same card, so a card never shows two
conflicting explanations.
Consequences: preserves the dashboard's four-tile invariant (On track + At risk + Blocked =
Active) — the previous "brief" proxy for the whole tile is gone; brief-readiness is now
correctly scoped to one of four inputs. The two block sources seed data doesn't naturally
exercise were verified directly against the live database with a row's state temporarily
forced and reverted, both producing a single correctly-worded flag.

## 044 — REVIEW_02.md P7: copy sweep, `?ref=` tracking, mobile pass
Date: 2026-08-31
Decision: Three independent items.
**Copy** — fixed the real database-vocabulary leaks the audit tool was flagging ("rows" →
"market versions"/"projects" in the affected screens); one flagged item turned out to be a
non-visible Jinja attribute access the audit's text-extraction can't distinguish from
rendered copy, confirmed by reading the template and left alone.
**`?ref=` tracking** — a logging middleware records `ref=<value> path=<path>` at INFO level
when the param is present. No new table or page — Render's own log viewer is the count-hits
mechanism, simpler than persisting a number that's wiped on every cold-start reseed anyway.
**"Never on page load" (AI calls)** — checked before touching anything: every AI call site is
either inside a POST handler, or on the two dashboard/timeline GET routes, calls a function
that's synchronous Python with no network I/O under the mock provider production actually
runs. Timed all six pages locally: 8–24ms each. The review's "pages timed out" symptom is
real, but the evidence points at Render free-tier cold start, not an in-request AI call —
flagged to the owner rather than silently built or dropped, since the review's suggested fix
targets a cause that isn't present and would cost the dashboard's most distinctive narration
for no reason.
**Mobile** — the actual blocker was upstream of anything the review's per-page list named:
the nav bar forced every page to 912px minimum width regardless of that page's own layout,
confirmed with a 375px-viewport check before any other change. Fixed the nav first
(horizontal scroll instead of wrapping), then applied the review's own per-page fixes (tables
wrapped in scroll containers; the pipeline board given a horizontal snap-carousel on small
screens, per the review's own sanctioned option).
Consequences: verified with a before/after viewport check across all seven screens (537px of
horizontal overflow before the nav fix, 0px after) and the full test suite.

## 045 — DEMO_SCRIPT.md re-verified against the running app, and a real P6.3 bug it surfaced
Date: 2026-09-01
Decision: Ran every step of DEMO_SCRIPT.md live against a fresh reseed rather than reading it
against the code. Two steps had gone stale from V2 work already landed; a third pointed at a
real product bug, not a script problem.
**Step 2 rewritten** — decision 038 scoped the readiness gate to projects with a brief
analysis, but no seeded project has one, so the script's own gate-refusal demonstration
silently succeeds now. Swapped it for decision 039's reason-required rule instead (attempting
On Hold with no reason is refused) — the same beat, a refusal that still fires reliably on
fresh seed data.
**Step 4 rewritten** — decision 041 changed the resource recommendation from one narrative
sentence to a ranked option list; the script's quoted paragraph no longer exists. Rewrote the
quote to the actual live text; the underlying numeric claims were still exactly right, only
the framing needed fixing.
**Step 7 — the real bug.** A pipeline card's "Blocked" badge didn't clear after the risk that
caused it was resolved. Traced to decision 043's cause 4 (a started phase with nobody
assigned): it excluded milestones and roleless phases, but not phase *kind* — so
prep/review/delivery phases were flagged right alongside production ones, even though only
production phases can ever be staffed. This wasn't demo-data noise: every one of the six
demo-scheduled projects has an early prep-kind phase that starts before "today" by
construction and is never auto-staffed, so 4 of 6 were flagged blocked on every single reseed
for a reason nobody could act on. Fixed by filtering `build_blocked_snapshot()` to
production-kind phases only, matching the actual staffing mechanism's own scope.
Also fixed alongside it: a seeded localisation row that incidentally also tripped the
"stalled" cause, unrelated to the deliberate demo bottleneck — changed its status so it stops
masking the real beat. And corrected the script's description of a badge's wording and
colour, which had never quite matched what actually renders.
**Step 1 reworded, not fixed** — a pre-existing fragility already named in decision 037 just
happened to show today: a deadline sitting right on the edge of the attention window flips in
and out depending which weekday the seed runs on. Reworded to state the reliable core count
and note the day-dependent one, rather than touching the seed date (already tried once, in
037, and reverted after it broke schedule feasibility elsewhere).
Consequences: steps 3, 5, 6, 8 verified live, unchanged. Every rewritten step re-run live end
to end after the fixes, against a fresh reseed.

## 046 — REVIEW_03.md R1 audit ran first, and it re-scoped the review
Date: 2026-09-02
Decision: Before touching any code, audited every model column that stores a value derived
from other rows (REVIEW_03.md R1's own instruction), then re-scoped the review against the
result rather than executing R1 as originally written. The audit found the stored-value list
short — most of what `REVIEW_02.md` P3 already fixed (012, 019, 021, 032, 034, 042, 043, 045)
— and found that three of R1's five confirmed symptoms are not stored-value drift at all:
`dashboard.py`'s at-risk filter excludes the "brief" cause outright (a live filtering gap);
`summarize_by_market()` computes its headline from one row and its translator list from every
row in the market (a live aggregation-granularity bug); and `/brief/analyse` already
recomputes from scratch on every submission — the "stale" score is `mock_analyse_brief`'s
rigid deadline/approval-owner regex matching, not a stored result. Only two symptoms were the
audited kind: `Project.project_type_id`/`estimated_days` were never written by `brief.py`'s
Full Brief flow, so a Brief-Assistant-created project could never generate a schedule or be
caught by the Blocked tile's brief-stalled check (REVIEW_03.md R6, the same root cause).
Re-scoped R1 into a five-item sequence, one commit each: (1) consolidate project creation —
done; (2) dashboard at-risk filtering; (3) mock extraction quality, combined with R10's
identical-output problem since both are the same thin-mocks weakness; (4) the localisation
card's aggregation bug; (5) the actual stored-column cleanup R1 originally asked for.
`REVIEW_03.md` rewritten in place — R1 marked superseded with the audit's findings and the
five-item plan, R6 marked done, and every place that cross-referenced "R1" (R5.1, R7, R8's
coverage note, R11) updated to point at the specific item that now covers it, per the owner's
instruction that a future reader should find the current plan, not the abandoned one.
Alternatives considered: running R1 as originally scoped (delete-and-recompute across the
audited columns) without re-checking it against the five confirmed symptoms first.
Why: the owner asked for the audit specifically so its length could determine how the rest of
the review gets sequenced, on the stated premise that a wrong root-cause guess costs more than
the audit itself. The audit proved the premise: two of the five symptoms had a completely
different class of cause (a filter, a mock's regex) that no amount of "find derived columns
and compute at render" would have touched.
Consequences: item 1 (project creation) is committed — see `app/services/project_creation.py`
and the seed backfill. A follow-up surfaced during item 1 verification: scheduling every seed
project surfaced two more real bugs — a latent nondeterminism in `resolve_project_type_id`
(iterating a set of strings, whose order isn't stable across process runs) and a feasibility
check that always compares a schedule's start against *today* rather than the deadline, which
made a Delivered or Approved project's "behind schedule" number grow without bound regardless
of when it actually finished. Both fixed in the same follow-up commit
(`NOT_ASSESSED_FOR_FEASIBILITY`, `app/services/scheduling.py`). Timeline coverage: 6 of 12 to
10 of 12 — the remaining two are still-vague Brief-status projects with no Deliverable rows to
infer a type from, left unscheduled rather than invented. DEMO_DATA.md's five required
conflicts re-verified against a running server after both commits: unchanged. Two pre-existing
test failures in `tests/test_assignment.py`, unrelated to any of this work, found during
verification and parked — to be diagnosed (real bug vs. stale test) after item 5, not fixed or
silently deleted before then.

## 047 — REVIEW_03.md item 2: at-risk tile no longer drops the "brief" cause
Date: 2026-09-02
Decision: `dashboard.py`'s `at_risk_ids` used to be `entry["cause"] in ("capacity",
"localisation", "deadline")` — silently excluding the "brief" cause. Now every project in the
attention snapshot counts as at risk unless it's already counted as blocked, with no
per-cause filter at all.
Alternatives considered: none — the comment already sitting next to the old code said the
four causes were meant to partition every active project across the three tiles exactly once;
the filter just didn't implement that.
Why: a project flagged in the "Needs attention" panel for a low readiness score counted
toward neither At Risk nor Blocked (the blocked-side brief-stalled cause needs
`estimated_days`, not always set) and read as on-track — the exact "0 at risk alongside 5
blocked" symptom the R1 audit traced to this file.
Consequences: added a regression test (confirmed it fails against the reverted filter before
restoring the fix). Verified live against the full seed data: On track 4 + At risk 2 +
Blocked 5 = Active 11.

## 048 — Timeline: unscheduled-project reasons and the tile-partition invariant test
Date: 2026-09-02
Decision: Two additions, requested together. (a) `/timeline` now lists projects with no
`project_type_id` in a "Not yet scheduled" footnote naming why ("no deliverables defined
yet", or "deliverables don't match a known project type") instead of omitting them
silently. (b) A regression test locks `on_track + at_risk + blocked == active` against the
full seed data.
Alternatives considered: none for either — both were specified directly.
Why: an absent project reads as a bug; a stated reason reads as the system knowing its own
limits. The three dashboard tiles disagreed with each other across two review rounds
(REVIEW_02.md P2, REVIEW_03.md R1/item 2) before decision 047 reconciled them — worth locking
down as a test now that it's true, not just re-verified by hand each time.
Consequences: none beyond the two additions — no schema or route behaviour changed.

## 049 — REVIEW_03.md item 3: widen mock.py's brief extraction and insight mock
Date: 2026-09-02
Decision: Mock mode is what gets demoed, so its output quality is the product as far as any
viewer is concerned. Two independent widenings:
1. **Brief extraction** (`mock_analyse_brief`): deadline recognition covers ISO, "16
   March"/"March 16", DD/MM(/YYYY) and weekday formats (was weekday-only), each hedge-checked
   against only its own sentence rather than the whole brief; vague windows ("mid-January",
   "spring next year", "end of next week") are captured as a stated target window instead of
   discarded. Approval-owner matching covers six phrasings (was one regex), each
   hedge-checked on its own captured clause. Added `LocalisationNeed.deadline` as a real
   extracted fact, and `score_readiness`'s `localisation_deadline` check now reads it
   directly instead of proxying off the project's overall deadline plus target-market
   presence. Markets expanded from 5 to 16, with 2-letter codes matched case-sensitively
   against the original text (lowercasing made several codes collide with common English
   words — it/be/at/no/ie). `format_specs` now requires every deliverable to carry a format,
   checked per deliverable type in its own clause, not any single global match.
2. **Insight mock** (R10): `compute_market_comparisons` aggregates CTR across every brand in
   a market by design (that's what keeps its sample size, and the significance gate,
   meaningful) — the actual bug was that `intelligence.py`'s `recommend()` route called
   `insight_to_action` with that brand-blind object instead of the brand-aware `facts` dict
   built right next to it. Added `compute_brand_breakdown()`, layered on top of (not
   replacing) the market-wide gate.
Alternatives considered: brand-scoping `compute_market_comparisons` itself — rejected, since
the seed data's ~2-row-per-brand groups would fall below the significance threshold and block
the demo's own DE recommendation flow entirely.
Why: both are the same underlying weakness — thin mocks in the mode that gets demoed — fixed
together per the owner's instruction.
Consequences: verified against a real 16-market acceptance brief end to end (see
`tests/test_brief_extraction_acceptance.py`): all 16 markets, 16 March recognised as a hard
date, score lands at 75, and editing the brief to add an approval owner and localisation
deadline moves the score 75→85 — the original R5.1 bug. All 12 seed briefs re-checked
identical before/after. Insight mock verified live: DE now returns three genuinely different
CTR readings per brand instead of identical text, each with an honest small-sample caveat.
`RUBRIC_WEIGHTS`'s `localisation_deadline`/`format_specs` semantics changed — `tests/
test_brief_rubric.py` updated to match, not left contradicting the new behaviour.

## 050 — REVIEW_03.md item 4: full pass on the localisation page (R7)
Date: 2026-09-02
Decision: `summarize_by_market()`'s `MarketSummary.translator_ids` now only ever names
translators covering the *same* rows `headline` describes — empty when at risk (naming
translators on other rows would recreate the exact contradiction being fixed), populated
from the in-flight rows specifically when the queue is just moving. Added
`flagged_localisation_id` so the UI can act on the specific row an at-risk headline is about.
Market cards on `/localisation` now link to `?market=X`, filtering the grid below (the link
wraps only the read-only summary, never the assign form, so no control nests inside it); an
at-risk card carries its own "Assign translator" form posting to the existing
`/localisation/{id}/assign` route.
Alternatives considered: none recorded — the three sub-items (output shape, clickable cards,
inline action) were specified directly, scoped to all of R7 except the translator-pool part,
which depends on R2 and was explicitly deferred.
Why: `headline` describing one row and `translator_ids` aggregating every row in the market
was the literal cause of the DE card reading "no assigned translator" next to "assigned to
Jonas and Camille" — two different rows presented as one fact. A card reporting a problem
with no way to act on it is the pattern this review has been removing everywhere else.
Consequences: six new tests (two unit, four route-level). Verified live against the seed
data: the FR card (the review's own example) now reads with no translator names and a
working assign control; the DE card reads "queue moving — 7 in flight, handled by Jonas,"
coherent since both halves describe the same rows.

## 051 — REVIEW_03.md item 5: stored-column cleanup, with one correction to R1's own audit
Date: 2026-09-03
Decision: `ProjectPhase.assigned_person_id` is computed live now — a new
`assigned_person_ids_by_phase()` (`app/services/assignment.py`) queries `Assignment` rows by
`project_phase_id` instead of reading a stored mirror. `assign_phase()`/`unassign_phase()` no
longer write it (nothing to sync — the Assignment row already was the source of truth);
`recommendations.py`'s resource-reallocation accept no longer needs its own sync step either,
since there's no second copy to update. `attention.py`'s blocked-snapshot cause 4 rebuilt on
the same live query. `Project.localisation_required` is computed live from the project's own
`Localisation` rows instead — `project_detail.html` already had the rows loaded; `pipeline.py`
now computes a `localisation_project_ids` set once per board render for `partials/_board.html`.
Deleted three genuinely dead columns: `Project.risk_level`, `Project.risk_reason` (no writer
anywhere, ever), and `ProjectPhase.status`/the `ProjectPhaseStatus` enum (written at creation
but never transitioned; its one reader, a `!= complete` filter, was vacuously always true
since nothing ever set `complete` — removed with no behaviour change).
**Not deleted, contradicting R1's own audit**: `Deliverable.status`. The audit said "no writer
anywhere" for this one — wrong. `seed.py` and `project_creation.py` both set it at creation
with varied, meaningful values (`in_progress`, `approved`, `delivered`, ...), and
`project_detail.html` displays it in the deliverables table. It's write-once (nothing
transitions it after creation) but it is read and it is real, demo-relevant information, not
a dead column computable from other rows — deleting it would have silently removed a working
feature to satisfy a mischaracterization from three items ago.
Alternatives considered: deleting `Deliverable.status` anyway, since it was named explicitly
in the plan.
Why: the plan's premise for every one of these four columns was "dead, safe to delete." Three
of the four hold; the fourth doesn't, and deleting it wouldn't be a cleanup, it would be a
regression to the deliverables table dressed up as one. Flagged rather than silently done or
silently skipped.
Consequences: 25 tests broke from the column removals (constructor kwargs, direct attribute
reads/writes) — all fixed to use the live-computed equivalents, none deleted. Two of
`test_assignment.py`'s failures are the pre-existing, parked ones (unchanged, still failing,
still not this decision's problem). Full suite otherwise green. Verified live against a fresh
reseed: all eight screens render, phase assign/unassign and the localisation "Yes/No" field
behave identically to before.

## 052 — The two parked test_assignment.py failures were a real bug, not a stale test
Date: 2026-09-03
Decision: `phase_candidates()`'s lead-time check —
`if phase.start_date < earliest_feasible_start(db, person, today): continue` — ran
unconditionally, for internal and external people alike. Now gated to `person.is_external`.
Why the two tests failed: both hardcoded a phase window of 2026-09-01 to 2026-09-03 with no
`today` argument, defaulting to the real clock. `earliest_feasible_start()` returns exactly
`today` for an internal person (no lead time) — once real time passed 2026-09-01, the check
`phase.start_date < today` started firing for every internal candidate, correctly by the
check's own logic, but the check's own logic was wrong.
Confirmed as a live, reachable bug before touching anything, not just a test artifact: queried
`phase_candidates()` against the real seed data's Winter Campaign Refresh — "Generation &
production," a phase already flagged Blocked by attention.py's cause 4 (started, nobody
assigned) — and it returned zero candidates, despite Priya, Elena, and Maya all having real
spare capacity. Timeline's own Assign control offered no one, internal or external, for a
phase the dashboard was simultaneously telling the producer was stuck. Exactly the "the tool
must never dead-end" failure R2.1 names, just found in the phase-assignment path instead of
the resource-recommendation one it was written about.
Alternatives considered: updating the two tests' hardcoded dates to relative ones and leaving
the check as-is — rejected once the live seed data reproduced the same zero-candidates result;
a passing test on top of a live dead end would have been the wrong fix.
Consequences: both parked tests pass again, and — because the fix removes the only
`today`-dependent branch internal-only test scenarios exercise — pass regardless of future
calendar drift, no date-relativization needed on their existing hardcoded dates. Two new
tests added, both pinning `today` explicitly rather than relying on the real clock: one
confirming an internal person is now offered for a phase already underway, one confirming an
external person's own lead time still gates the same phase (`engage_person()` enforces the
identical rule on accept, so the two must not disagree). Full suite: 217 passed, 0 failed.
Verified live: Winter Campaign Refresh's blocked phase now offers Priya, Elena, and Maya.
