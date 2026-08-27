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
  Same `capacity.py` computation, presentation only.
- **A2**: New `/localisation` screen — project × market grid, color-coded by stage, with a
  per-market summary (volume in flight, assigned translators, oldest item, risk flagged
  first). Dashboard's localisation tile now names the bottleneck instead of counting rows.
  New `summarize_by_market()` in `app/services/localisation_risk.py`, reusing the existing
  risk check rather than duplicating it.
- **A3**: Attention causes renamed to four canonical tags (`capacity` / `deadline` / `brief`
  / `localisation`), shown with consistent colours on both the Dashboard panel and Pipeline
  cards. Added a deadline rule: a project within 7 working days of its deadline still in an
  early pipeline stage (Brief/Ready/Assigned) is flagged. FEEDBACK_LOG.md's actual wording —
  "behind where the schedule implies it should be" — depends on the phase/schedule system
  from Session B (`PLANNING.md`), which doesn't exist yet; the pipeline-stage check is an
  honest interim proxy, documented in a code comment, to be revisited once that system lands.
- **A4**: Requesting a recommendation for a conflict that already has a pending one now
  replaces it only if the underlying facts changed; if unchanged, nothing is regenerated and
  the UI says so. Comparison is exact equality on the stored `computed_facts_json`.

Alternatives considered (A3): waiting for Session B before adding any deadline rule at all.
Why: the four items were independently scoped and shippable now; the schedule-derived version
can replace the proxy later without changing the attention-panel contract.

**Bug found and fixed while testing A4, not part of the four items:** `resources.py`'s
candidate-building had no role filter — when no candidate's skill tag matched the overloaded
person's, it fell back to whoever had the most spare capacity with no role check, and
recommended reassigning a design project to Jonas, an external translator. Same class of bug
fixed in Phase 4 for the Intelligence flow's candidate list; this was the sibling code path
that never got the same fix because nothing had exercised its fallback branch until now.
Excluded `producer` and `translator` roles from resource-reallocation candidates.

Consequences: None of this was pushed or deployed until the owner asked why the live demo
still showed the old behaviour — a reminder to say explicitly when work is local-only.

## 015 — Resolved two dangling references found before starting Session B
Date: 2026-08-27
Decision: (1) Moved `creativeops-docs-v2/{PLANNING,BRIEF_MODES,ASSUMPTIONS,FEEDBACK_LOG}.md`
into `docs/` and added all four to the doc table in `CLAUDE.md`, ahead of `FEEDBACK_LOG.md`'s
own "when starting Session B" housekeeping schedule — the directory was sitting uncommitted
on disk, so folding it in now was lower-risk than leaving it stray. (2) `BRIEF_MODES.md` and
`FEEDBACK_LOG.md` both referenced a `SUPERVISION.md` "check 4" that does not exist anywhere
in the repo or its git history. Owner confirmed the intended referent is the readiness-gate
refusal — `check_readiness_gate` and `validate_transition` in `app/routes/pipeline.py` — and
both docs were reworded to point at that code directly instead of a nonexistent file.
Alternatives considered: writing a new `SUPERVISION.md` to match the reference; leaving the
reference as-is with a flag to revisit before Session B.
Why: the owner picked the option that resolves the ambiguity now rather than deferring it.
Consequences: **A real gap surfaced while resolving this** — `check_readiness_gate` and
`validate_transition` had no automated test, despite `BUILD_PLAN.md` Phase 3's exit criteria
requiring "an invalid transition is refused with a reason." Closed immediately after: added
`tests/test_pipeline_transitions.py` (6 cases — skip-forward refusal, one-stage-forward
allowed, backward-always-allowed, low readiness blocks past Ready, readiness at threshold
passes, no-brief-analysis is ungated). `docs/FEEDBACK_LOG.md`'s note about the gap now reads
as historical rather than a live TODO.

## 016 — Session B step 1: ProjectType and PhaseTemplate models, seeded from PLANNING.md
Date: 2026-08-27
Decision: Added `ProjectType` and `PhaseTemplate` to `app/models/__init__.py` and a
`PhaseKind` enum (`prep`/`production`/`review`/`delivery`), plus `seed_phase_templates()` in
`app/seed.py`, seeding the four templates from `docs/PLANNING.md` (Film / branded content —
11 phases, Event — 8, Stills — 7, Social / AI-generated content — 7; 33 rows total). Called
from `seed.py`'s `main()` with its own idempotency check, independent of the existing
Person-count check. No UI, no `Project.project_type_id` column yet — per `FEEDBACK_LOG.md`'s
own sequencing, step 1 is models and seed data only. Added the entities to `DATA_MODEL.md`
(reference, not duplicate) and 6 tests in `tests/test_phase_templates.py`.
Alternatives considered: leaving `required_roles` blank until Session B needs it for real;
asking the owner to specify roles per phase before writing any seed data.
Why: two judgment calls were needed that `PLANNING.md`'s phase tables don't settle, and
neither seemed worth blocking on:
1. **`required_roles` per phase.** `PLANNING.md`'s tables (Phase/Days/Kind/Notes) have no
   role column, though `PhaseTemplate`'s own schema calls for one. Roles were inferred from
   each phase's name/notes against the existing `PersonRole` enum, which has no
   director/DP/fabricator roles — "producer" stands in for externally-vendor-coordinated work
   like shoot crews and fabrication builds. This is a placeholder, not a studio judgement call
   the way `ASSUMPTIONS.md`'s rate bands are — it should be reviewed once Session B actually
   uses these roles to build assignment candidates.
2. **Three rows list "milestone" as their `Kind`** (PPM, Fabrication cutoff, Running order
   meeting) — not one of the four `PhaseKind` values `PLANNING.md` itself defines. Reclassified
   each to the real kind whose boundary it sits on (PPM → review, since it's a client sign-off;
   Fabrication cutoff → prep, the gate before build starts; Running order meeting →
   production) and set `is_milestone=True` with `default_days=0` on those three only. `Final
   approval` also carries a "milestone at end" note but has 3 days of duration in the same
   table, so it stays `is_milestone=False` — a milestone marker attached to the end of a
   phase that has duration is a different thing from a zero-duration phase, and the schema
   only has one `is_milestone` flag per row, not a separate "milestone at boundary" concept.
Consequences: `required_roles` values are a placeholder inference, not a reviewed spec — flag
this explicitly if Session B step 5 (assignments derived from phases) is scheduled, since
that's the point these values start driving real capacity numbers. Nothing else in the app
reads these two tables yet, so getting the roles wrong here has no live-app consequence today.

## 017 — Owner review round 2: more approval checkpoints, budget sign-off, editability confirmed
Date: 2026-08-27
Decision: Updated all four phase templates in `app/seed.py` and `docs/PLANNING.md`
(43 phase rows total, up from 33):
- **Film**: added `Pre-PPM` (client-facing check-in) before the existing `PPM`; added
  `Budget sign-off` after `PPM` (also client-facing); added a second client review
  (`Client review 2`) after `Revisions`, alongside the existing one after `Offline edit`.
- **Event**: `is_client_review=True` on every phase except `Fabrication & build` and `Live`;
  added `Budget sign-off` after `Concept & design` (client-facing).
- **Stills**: added a `PPM` milestone (client approval of approach) after `Pre-production`;
  added `Budget sign-off` right after it (client-facing).
- **Social**: added `Brief approval` after `Brief & scoping`, `Concept approval` after
  `Concept & scripting`, `Budget sign-off` right after that (client-facing), and `Final
  approval` after `Revisions` — on top of the existing `Client review` after `Generation &
  production`.
- Confirmed two capabilities as requirements (documented in `PLANNING.md`, not built): a
  project's phase day counts become editable once a schedule exists, and producers can insert
  ad-hoc phase rows a template doesn't anticipate (e.g. "Sourcing talent" for a celebrity
  shoot) without writing back into the shared template.
Alternatives considered: building a minimal edit screen now, ahead of `FEEDBACK_LOG.md`'s own
step ordering (step 4, the timeline view, is where schedule UI was supposed to land). Also
considered, and reversed same-session: `Budget sign-off` and `Pre-PPM` were first drafted as
internal-only (`is_client_review=False`) on the assumption that budget approval is a
finance/business gate distinct from creative review — owner corrected this immediately, both
are client-facing, `is_client_review=True` on all four `Budget sign-off` rows and on Film's
`Pre-PPM`.
Why: the owner chose to document the editability requirement now and build it when there's an
actual schedule (`ProjectPhase` rows, step 3) to edit — editing a template with no generated
instance to preview against would need throwaway UI.
Consequences: "A week before" (Pre-PPM's timing relative to PPM) still isn't encoded as an
actual day gap — there's no back-scheduling logic yet to consume it (Session B step 2), so
today's row only fixes its position in sequence, not a duration offset; revisit once that
logic exists. All milestone rows added are 0 days, so `EXPECTED_TOTAL_DAYS` in
`tests/test_phase_templates.py` only changed for Film (32 → 35, from the one new
working-day phase, `Client review 2` at 3 days) — Event, Stills and Social keep their
original totals (27, 17, 11) even with new rows added, since every addition to those three
was a 0-day milestone. `EXPECTED_PHASE_COUNTS` updated for all four (14, 9, 9, 11).

## 018 — Session B step 2: back-scheduling service
Date: 2026-08-27
Decision: Added `app/services/scheduling.py` — a pure function, `back_schedule()`, taking a
project type's `PhaseTemplate` rows, a delivery date, and an optional volume factor, and
returning dated phases. No `ProjectPhase` model and no route touch this yet — step 3
("schedule generation on a project") is what will persist this function's output. 7 unit
tests in `tests/test_scheduling.py`, plus 6 pre-existing template tests, still passing.
Alternatives considered: computing review-phase durations from each `PhaseTemplate` row's own
`default_days`, matching what's stored; deferring anchored-phase handling entirely vs. noting
it explicitly as out of scope.
Why, three implementation choices worth flagging:
1. **Client-review-duration phases (`kind=review`, not a milestone) use a fixed
   `CLIENT_REVIEW_DAYS = 3` constant, not the template's stored `default_days`** — this is
   `PLANNING.md`'s point 6, "client review windows come from ASSUMPTIONS.md, not the
   template," taken literally. `ASSUMPTIONS.md`'s own editable table is Session C scope, so
   this is a fixed stand-in for that table's `client_review_days` value until then. **This
   has a real, visible effect today**: Stills' and Social's `Client review` rows are seeded
   with `default_days=2`, but the *scheduled* duration for both is now 3 working days — the
   template's stored value stays as the documented default (matches `PLANNING.md`'s table,
   which the owner reviewed), but scheduling doesn't use it. **Confirmed with the owner
   2026-08-27**, after seeing a rendered Stills and Social schedule at a real delivery date
   (30 Oct 2026) with the 2→3 day shift visible on both — the studio-wide 3-day policy,
   changeable in one place later, is the intended behavior, not the per-template value.
2. **Anchored phases are out of scope for this step.** `PLANNING.md`'s back-scheduling
   section describes them (an event's Live day, a shoot pinned to talent availability) as
   part of the same algorithm, but anchoring is a per-project-instance fact — it belongs on
   `ProjectPhase.is_anchored`, which doesn't exist until step 3. Building it now would mean
   designing an input shape with no real caller. Revisit when step 3 lands.
3. **Feasibility is data, not prose.** The doc's own example ("Working backwards from 14
   November, this project needed to start 6 November — 4 working days ago...") is written as
   a sentence, but that sentence is `assess_schedule_feasibility`'s job (step 6, AI-narrated
   from computed facts), not this service's. `back_schedule()` returns `is_feasible` and
   `shortfall_working_days` only — the same rule as everywhere else in this app: Python
   computes, the model explains.
Consequences: a past-start scenario is reported (`is_feasible=False`, a working-day count)
without altering any computed date — "never silently compress" holds structurally, since
there's no compression logic in this function at all; that arrives with
`assess_schedule_feasibility`'s options list in step 6.

## 019 — Session B step 3: schedule generation, ProjectPhase persisted
Date: 2026-08-27
Decision: Added `ProjectPhase` and a `ProjectPhaseStatus` enum (`not_started` /
`in_progress` / `complete`) to `app/models/__init__.py`, per `PLANNING.md`'s "Data model
additions". `Project` gained `project_type_id` (nullable FK) and `volume_factor` (float,
default 1.0). Added `generate_schedule(db, project)` to `app/services/scheduling.py`, which
runs `back_schedule()` against the project's type and deadline and persists the result as
`ProjectPhase` rows, replacing any existing rows for that project. 3 new tests (11 total in
`tests/test_scheduling.py`, 56 across the suite). No route or screen touches this yet —
Session B step 4 (timeline view) is where a generated schedule first becomes visible.
Alternatives considered: inferring `ProjectPhaseStatus`'s values from context vs. asking the
owner; a bulk `Query.delete()` for replacing a project's old schedule vs. an ORM-level
per-row delete.
Why:
1. **`ProjectPhaseStatus` values aren't specified anywhere** — `PLANNING.md`'s `ProjectPhase`
   row list names the field but not its values. Inferred `not_started`/`in_progress`/
   `complete` to match the shape `Deliverable` and `Localisation` already use in this app.
   Low-stakes and easily revisited (nothing reads this field yet), so not worth a question.
2. **The "replace, don't duplicate" delete used `Query.delete()` first, and that was a real
   bug**, not a style preference: SQLite reuses rowids after a bulk delete, and a bulk
   `Query.delete()` doesn't remove the deleted rows' Python objects from SQLAlchemy's session
   identity map. Regenerating a schedule then raised `SAWarning: Identity map already had an
   identity for (...)` on every row, because the newly-inserted replacement rows landed on
   the same primary keys as the just-deleted ones while the session still thought those keys
   belonged to the old (deleted) objects. Fixed by querying the existing rows and calling
   `db.delete()` on each — the ORM-tracked path — instead of the bulk query.
Consequences: local dev's existing `creativeops.db` didn't have the two new `Project` columns
or the `project_phases` table — `Base.metadata.create_all()` only creates missing tables, it
doesn't `ALTER` existing ones. Ran `python -m app.seed --reset` to rebuild the local file;
confirmed all six screens still render against the reset database. Render's deploy is
unaffected — decision 013 already has it reseeding from a blank file on every boot, so it
picks up the new schema automatically on next deploy. `Project.project_type_id` stays
unset for all seeded/existing projects; nothing in the Brief Assistant's create-project flow
sets it yet.

## 020 — Session B step 4: the timeline view
Date: 2026-08-27
Decision: Added `/timeline` (`app/routes/timeline.py`, `app/templates/timeline.html`) and a
new positioning-math module, `app/services/timeline.py`, scoped to exactly what
`FEEDBACK_LOG.md`'s step 4 names: projects down the left, weeks across the top, phase bars
coloured by `kind`, milestones as diamonds, a today line. Filters (brand/market/type/owner)
came from `PLANNING.md`'s fuller Timeline view spec and mirror the existing filter pattern on
Pipeline and Localisation. Per-project rows collapse by default (one bar-track per project,
which already reads cleanly since a project's own phases never overlap) and expand via an
Alpine `x-show` toggle into a per-phase table — the "click to expand into per-phase rows"
requirement. A hand-built CSS bar chart, not a Gantt library, per `PLANNING.md`'s explicit
instruction. 8 new tests in `tests/test_timeline.py` (64 across the suite); all seven screens
re-verified via `TestClient`, and the rendered HTML inspected directly (bar/week percentages,
row ordering) since no browser automation was available in this session — flagging that
explicitly rather than claiming a visual check that didn't happen.
Deliberately **not** built here, both because `FEEDBACK_LOG.md`'s step 4 doesn't name them and
because they depend on state that doesn't exist yet:
- **Conflict-outlined bars** ("a phase bar is outlined as a conflict when a role it requires
  has no person with capacity in that window") — `ProjectPhase.assigned_person_id` is always
  null until step 5 derives assignments from phases; there's nothing to check capacity against
  yet.
- **The milestone meeting list beside the timeline** — that's step 7 by name.
- **Any feasibility messaging on-screen** — `back_schedule()`'s `is_feasible`/
  `shortfall_working_days` aren't surfaced here at all. Saying that plainly, per `PLANNING.md`'s
  "when the computed start is in the past" instruction, is `assess_schedule_feasibility`'s job
  (step 6, AI-narrated from computed facts) — the bars simply render wherever their dates land,
  including left of the today line when a schedule doesn't fit.
Alternatives considered: inventing new demo projects to populate the screen vs. giving three of
the existing twelve a `project_type_id`; picking those three for thematic fit alone vs. also
checking feasibility.
Why: `DEMO_DATA.md` fixes the seed at 12 projects — adding more would contradict a documented
"Scale" decision, so three existing projects were typed instead, with their `DEMO_DATA.md`
deadlines left completely untouched. Candidates were screened against two rules: (1) never
touch Winter Campaign Refresh or Loyalty Relaunch Teaser's deadlines or type them for this —
those two carry `DEMO_DATA.md`'s required capacity-overload/reassignment conflict, and Winter
Campaign Refresh's deadline is explicitly named ("one deadline this week") as load-bearing for
it; (2) prefer a spread of feasibility outcomes over uniformly comfortable ones, since a
mildly- or badly-infeasible schedule is exactly the honest scenario `PLANNING.md`'s
back-scheduling section describes, not a bug to hide. Final picks, checked by computing actual
calendar days from today against each template's total working-day need: **Mother's Day
Static Set** → Social (deadline 24 days out against ~15-16 needed — comfortably feasible),
**Spring Lookbook** → Stills (15 days out against ~24 needed — mildly short, and the best
thematic fit for a photography template), **Autumn Prints FR Push** → Film (10 days out
against ~49 needed — badly short, but it exercises the largest template, 14 rows, on screen).
No seeded project describes a physical event, so Event has no demo instance; the screen
doesn't need every type represented to prove itself.
Consequences: three of the twelve V1 demo projects now also carry a `project_type_id` and a
generated `ProjectPhase` schedule; nothing about their status, deadline, assignments, or
localisation rows changed, so their role in `DEMO_DATA.md`'s five required conflicts is intact.
Reset the local dev database again (new table, same reason as decision 019).

## 021 — Session B step 5: assignments derive from phases
Date: 2026-08-27
Decision: Added `app/services/assignment.py` (`phase_candidates()`, `assign_phase()`,
`unassign_phase()`) and wired an Assign/Unassign control into `/timeline`'s per-phase expand
view. `ProjectPhase` gained `required_roles` (copied from the source `PhaseTemplate` row by
`generate_schedule()`) and `Assignment` gained a nullable `project_phase_id`, so a
reassignment can find and replace exactly the row it produced rather than guessing among a
person's other assignments on the same project. `app/services/capacity.py` was **not
touched** — confirmed by a route-to-Resources-screen check (assign a phase in the running
app, then load `/resources` and see the same person's allocation reflect it), matching
`PLANNING.md`'s own promise for this step. 20 new tests (10 in `tests/test_assignment.py`, 6
more in `tests/test_timeline.py`, 77 across the suite).
Alternatives considered: auto-picking a person deterministically inside `generate_schedule()`
instead of surfacing candidates for a human to choose from; a phase-derived assignment
allocated at 100% (one person, fully dedicated) instead of 50%; checking a candidate's
capacity only at the phase's start date instead of across its whole window.
Why, three real decisions:
1. **A human still clicks Assign — nothing auto-picks a person.** `PLANNING.md`'s "creates a
   candidate assignment" reads ambiguously between "proposes a candidate" and "commits an
   assignment automatically." Given `CLAUDE.md`'s non-negotiable that AI recommends and
   humans decide, and this codebase's existing candidate-then-click pattern (`resources.py`'s
   reassignment flow), auto-picking a specific person felt like the wrong default even for
   non-AI deterministic logic — a phase's assignee is a real staffing decision, not just
   arithmetic.
2. **The phase-assignment allocation default started at 100%, and that was a real problem,
   not a style choice.** Checked against the actual seeded roster (`DEMO_DATA.md`'s people
   are mostly 20-55% allocated already, never fully free) before finalizing: at 100% required,
   `phase_candidates()` returned empty for most of the three demo projects' production phases
   — the feature would have looked broken on first use. Lowered to 50 ("a phase is usually a
   significant piece of someone's workload, not the whole of it"), verified empirically that
   6 of 9 production phases across the three demo schedules then found at least one candidate.
3. **`assign_phase()` refuses milestones and non-`production`-kind phases outright**, reading
   `PLANNING.md`'s "each production phase requiring a role" literally — a milestone is a
   0-duration meeting, not assignable work. Also refuses a role mismatch, the same rule
   `DECISIONS.md` 014 fixed for the resource-reallocation candidate list.
4. **Capacity is checked across the phase's full date window** (via `capacity.py`'s existing
   `allocation_timeline()`, composed not duplicated), not just its start date — a multi-day
   phase can run into a person's other commitments partway through, and a start-date-only
   check would miss that. Point-in-time checks are the existing convention elsewhere in this
   app (`person_capacity()`, `_build_conflict_facts()`); window-max is more correct here
   specifically because production phases commonly span several days, unlike the rest of the
   app's mostly point-in-time question ("is this person overloaded right now").
Consequences: assigning someone who's already tight or overloaded elsewhere is still possible
if a producer overrides past what `phase_candidates()` offers (verified in
`test_overload_created_by_a_phase_assignment_is_visible_to_get_conflicts`) — `capacity.py`'s
existing conflict detection catches it on the Resources screen exactly as it would any other
overload, which is the intended integration, not a gap. Reset the local dev database again
(two new columns).

## 022 — Session B step 6: assess_schedule_feasibility, the first Session B AI function
Date: 2026-08-27
Decision: Added `app/services/ai/feasibility.py` (`assess_schedule_feasibility`), its
`ScheduleAssessment`/`ScheduleOption` schemas, mock, and prompt — the sixth AI function,
following the existing five's exact plumbing (`client.py`/`mock.py`/`prompts.py`/wrapper
file). The deterministic facts it consumes come from a new
`app/services/scheduling.py::build_feasibility_facts()`, not from the AI layer — same rule as
everywhere else: Python computes, the model narrates. Wired into `/timeline` (a red "Behind"
badge plus a full statement-and-options panel per project, styled like the existing
localisation-risk panel on project detail) and `/dashboard` (a new "Schedule" tile, styled
like the existing Localisation tile). Only called for a project whose generated schedule
doesn't fit its deadline — a feasible one has nothing to narrate, so no call and no panel.
14 new tests (5 for `build_feasibility_facts()` in `tests/test_scheduling.py`, 5 for the AI
wrapper/invention-guard/mock in `tests/test_ai_feasibility.py`, 2 route tests in
`tests/test_timeline.py`, 2 in the new `tests/test_dashboard.py`), 91 across the suite.
Alternatives considered: letting the model choose `shortfall_days`/`options` itself instead
of overwriting them after parsing; computing `binding_constraint` deterministically in Python
instead of letting the model pick from candidates; attempting the third compression priority
("overlap phases that don't strictly depend on each other").
Why, three real decisions:
1. **Every number is recomputed from the facts after parsing, never trusted from the
   response** — `feasible`, `shortfall_days`, and the entire `options` list are overwritten
   unconditionally, the same treatment `recommend_resource`'s `impact` figures get on
   accept. `binding_constraint` is the one field left to the model, and only because
   `PLANNING.md` says so explicitly ("the model chooses which constraint to name as
   binding") — even then it's validated against the given
   `binding_constraint_candidates` after parsing and corrected to Python's own top
   candidate if the model names anything else (`test_invention_guard_rejects_a_binding_
   constraint_not_in_candidates`).
2. **`binding_constraint_candidates` are Python's top 3 non-milestone phases by working-day
   count**, not a single forced answer — this gives the model a real (bounded) choice to
   make, consistent with how `recommend_resource` already hands the model a feasible
   candidate list rather than a single answer.
3. **The third compression priority is not attempted.** `PLANNING.md`'s compression order
   is review windows, then revision phases, then phase overlap, then "flag not achievable."
   The first two are computed (`compress_review` from `ASSUMPTIONS.md`'s
   `client_review_minimum_days`; `drop_revisions` for any phase named "revision", full
   removal, matching `PLANNING.md`'s own worked example — "drop the revisions phase," not a
   partial trim). The third needs a phase dependency graph — nothing in this data model
   records which phases can run in parallel — so it's left out rather than guessed at.
   "Flag not achievable" is what the whole panel already does when no option closes the gap.
Consequences: `move_delivery`'s recovered days always exactly close the shortfall (it's
defined that way — the new date is `shortfall_days` working days past the current deadline);
`compress_review` and `drop_revisions` may each recover less, and nothing sums them or
picks a combination — the panel lists independent moves for a producer to weigh, not a
solved plan. Verified against the real seed data, not just synthetic tests: both of the
Timeline's infeasible demo projects (`Spring Lookbook`, `Autumn Prints FR Push` — decision
020) now show a real computed shortfall and options on both screens.
