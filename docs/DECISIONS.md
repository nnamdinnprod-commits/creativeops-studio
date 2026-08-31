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

## 023 — Session B step 7: milestone meeting list, Session B complete
Date: 2026-08-27
Decision: Added `milestone_list()` to `app/services/timeline.py` — a pure function over the
same `projects_with_phases` the route already builds for the bar chart, so the meeting list
respects whatever brand/market/type/owner filter is active rather than showing an unfiltered
superset. Sorted chronologically (start date, then project name, then phase name for stable
ties). Rendered as a new sidebar card on `/timeline`, restructuring the page into a
`md:flex` layout: the bar chart (unchanged, still horizontally scrollable on its own) on the
left, a fixed-width "Milestone meetings" card on the right, each entry linking to
`/projects/{id}`. 2 new tests in `tests/test_timeline.py`, 93 across the suite. This was the
last step in `FEEDBACK_LOG.md`'s Session B sequence — Session B is now complete end to end
(steps 1–7), logged in `FEEDBACK_LOG.md`.
Alternatives considered: dropping past milestones from the list entirely; querying fresh from
the database inside `milestone_list()` instead of reusing the route's already-filtered
`projects_with_phases`.
Why:
1. **Past milestones stay in the list, visually muted (`opacity-50`), not dropped.** A
   milestone that should already have happened is real information — especially now that
   step 6 already shows some of these same projects as behind schedule — not noise to hide.
   Dropping it would silently disagree with the "Behind" badge sitting right next to it in
   the same view.
2. **`milestone_list()` takes the already-loaded, already-filtered phase data** rather than
   querying the database itself, the same shape as `build_timeline()` right above it in the
   same file. One filter pass in the route now drives both the chart and the list — they can
   never silently disagree about which projects are in scope.
Consequences: none beyond the two functions sharing one input — no new schema, no new route.
`PLANNING.md`'s remaining unbuilt item for the Timeline view is the conflict-outline rule
(a phase bar outlined when its required role has no one with capacity in that window); step
5 built the assignment data this would read, but nothing consumes it for this yet — a real,
still-open gap worth a look before calling the Timeline view entirely finished, separate from
Session B's own step list which is now fully done.

## 024 — Conflict-outline rule closed: PLANNING.md's Timeline view now fully built
Date: 2026-08-27
Decision: Added `conflicted_phase_ids()` to `app/services/timeline.py` — takes the route's
already-computed `candidates_by_phase_id` (from `app/services/assignment.py`'s
`phase_candidates()`, step 5) and returns the set of phase ids with an empty candidate list.
Wired into `/timeline`: a red ring (`ring-2 ring-red-600`) on any unassigned production
phase's bar with no one who could realistically take it on, visible in the collapsed view
without expanding a row — a bar's tooltip also states the reason. Legend entry added. 5 new
tests (2 pure-function, 3 route-level), 98 across the suite. Verified against the real seed
data: 3 phase bars across the three demo schedules are flagged, all in roles this studio's
roster is thin on (motion design).
Alternatives considered: also checking assigned phases for whether their assignee has since
become overloaded elsewhere; querying the database fresh inside `conflicted_phase_ids()`
instead of reusing the route's already-computed dict.
Why:
1. **Only unassigned phases are checked.** PLANNING.md's literal wording is "a role it
   requires has no person with capacity" — a staffing-gap fact, not an overload fact. Once a
   phase has an assignee, the gap is closed by definition; whether that specific person is
   now stretched thin elsewhere is a different, already-covered question (`capacity.py`'s
   `get_conflicts()`, surfaced on the Resources screen and the dashboard's capacity tile).
   Conflating the two would make this rule redundant with a screen that already does it
   better, and would flicker a phase's outline on and off based on unrelated assignments
   elsewhere in the portfolio — confusing for a rule that's supposed to answer "is this
   specific piece of work staffable."
2. **`conflicted_phase_ids()` takes the dict, not the database.** The route already builds
   `candidates_by_phase_id` for the assign-picker UI (step 5); recomputing `phase_candidates()`
   a second time for the same phases would double the query cost and risk the two checks
   silently disagreeing if one code path changed without the other. One computation now
   drives both the picker and the outline.
Consequences: this closes the last open item from `PLANNING.md`'s Timeline view section —
every bullet in that spec is now built, not just Session B's own numbered step list.
`DECISIONS.md` 020's original "except the conflict-outline rule" caveat no longer applies.

## 025 — Session C step 1: Assumption and RateBand tables, editable screen
Date: 2026-08-27
Decision: Added `Assumption` and `RateBand` models, `app/seed.py`'s `seed_assumptions()` (21
`Assumption` rows across the four categories `ASSUMPTIONS.md` names, 6 `RateBand` rows — one
per `PersonRole`), `app/services/assumptions.py` (`get_value`, `get_rate_band`, `reset_all`),
and `/assumptions` — a grouped, inline-editable table plus a "reset all to defaults" button,
following the exact plumbing pattern established for every other screen this session (thin
route, deterministic service, Jinja template, nav link). 13 new tests in
`tests/test_assumptions.py`, 111 across the suite.
Alternatives considered: wiring `app/services/scheduling.py`'s hardcoded `CLIENT_REVIEW_DAYS`/
`VOLUME_SCALE_BANDS` constants to read live from this table as part of this same step;
modeling "Confidence bands" as a dedicated two-column table instead of flattening it into
paired `Assumption` rows.
Why:
1. **Not wiring Session B's constants to this table now, deliberately.** `ASSUMPTIONS.md`'s
   "Changing a value recomputes any open estimate or schedule immediately" is a real
   requirement, but there's no "open estimate" yet to recompute — that's Quick Estimate mode
   (step 2), the actual payoff moment for "editable, recomputes." Retrofitting Session B's
   already-tested, already-committed `back_schedule()`/`volume_factor_for()` in the same step
   that introduces the new tables would mean two different kinds of change (new feature +
   refactor of settled code) landing together, with no visible demo moment to justify the
   risk yet. `ASSUMPTIONS.md` and `DATA_MODEL.md` both say so explicitly now, rather than
   silently leaving the gap implicit. Revisit when step 2/3 actually need it.
2. **"Confidence bands" flattened to one `Assumption` row per number**, not a dedicated
   two-column table. `ASSUMPTIONS.md`'s own `Assumption` schema gives every row exactly one
   `value_numeric` — the source table's low/high-factor pairs (`high` → 0.95/1.10, etc.)
   become two rows each (`confidence_high_low_factor`, `confidence_high_high_factor`, ...),
   8 rows total. Matches the doc's literal data model rather than inventing a second table
   the doc doesn't ask for.
3. **`RateBand` has no reset-to-defaults behavior** — `ASSUMPTIONS.md`'s own `RateBand`
   columns (`id, role, low, high, currency`) have no `default_value` field, unlike
   `Assumption`. A changed rate stays changed until edited back by hand; "reset all to
   defaults" only touches `Assumption` rows. Followed the doc's data model rather than adding
   a column it doesn't specify.
Consequences: editing a value on `/assumptions` today only changes that stored number —
verified this is honestly labeled in `ASSUMPTIONS.md` rather than implying live effect. The
screen is real and functional (seeded, editable, resettable, tested) but inert until step 2
reads from it.

## 026 — Session C steps 2–4: Quick Estimate mode, Session C complete
Date: 2026-08-27
Decision: Built Quick Estimate mode in full — steps 2, 3, and 4 landed together rather than
sequentially, since costing (3) and the prominent `single_best_question` callout (4) are
naturally part of the same screen and the same deterministic pass over phase templates as
duration (2), not separable work. Added:
- The 7th AI function, `quick_estimate` (`app/services/ai/estimate.py`,
  `QuickEstimate`/`QuickEstimateAssumption` schemas, mock, prompt) — reads raw text and infers
  the request's shape, closer in kind to `analyse_brief` than the six facts-narrating
  functions, since there's no pre-computed fact set for it to narrate around.
- `app/services/estimate.py`'s `compute_estimate()` — deterministic duration, cost, and
  earliest-delivery calculation reading `Assumption`/`RateBand` live via
  `app/services/assumptions.py` (step 1's real payoff moment) and the matched `ProjectType`'s
  `PhaseTemplate` rows.
- `/brief` now defaults to Quick Estimate mode, with Full Brief moved behind `?mode=full` —
  the Full Brief routes/logic are otherwise untouched (`app/routes/pipeline.py`'s readiness
  gate, `check_readiness_gate`, still stands exactly as `BRIEF_MODES.md` requires between an
  estimate and a commitment).
- Recompute is pure Python: editing asset count, the photography toggle, review rounds, or
  confidence resubmits to `/brief/quick-estimate/recompute`, which never calls the model
  again — state that must survive the round trip (raw text, work type, markets, the AI's
  `single_best_question`/`caveats`) travels via hidden form fields, not a new DB table.
34 new tests (`tests/test_estimate.py`, `tests/test_ai_quick_estimate.py`,
`tests/test_quick_estimate_route.py`), 137 across the suite.
Alternatives considered: building steps 2–4 as three separate, sequential commits; scaling
volume only for `PhaseTemplate` rows already flagged `scales_with_volume`; persisting
QuickEstimate results in a new table so they could be revisited later.
Why, two real decisions and one bug caught before it shipped:
1. **A real, pre-existing gap surfaced immediately while wiring this up**: only Film's
   `PhaseTemplate` rows carry `scales_with_volume=True` (`DECISIONS.md` 016) — Event, Stills,
   and Social have none. First-pass testing showed asset count doing *nothing* to the
   estimate for "social," `BRIEF_MODES.md`'s own primary worked example. Fixed by making
   Quick Estimate's own volume rule coarser and self-contained: every production-kind phase
   scales, not only rows carrying the flag. This is a deliberate divergence from
   `back_schedule()`'s per-phase flag (documented in both `BRIEF_MODES.md` and this entry),
   not a fix to Session B's code — that flag stays exactly as tuned for precise generated
   schedules; Quick Estimate is a coarser tool by nature and gets its own, simpler rule.
   Regression-tested across all four work types (`test_asset_count_affects_duration_for_
   every_work_type`).
2. **Costing compounds two sources of range**, not one: each cost line's low/high first
   comes from that role's own `RateBand` range, and the confidence factor then widens that
   already-ranged sum further. `BRIEF_MODES.md`'s formula (`range = sum(lines) ×
   (low_factor, high_factor)`) reads as a single point sum widened once; duration has no
   rate-band range to start from, so its low/high genuinely is just the confidence factor
   applied to one number. Documented explicitly in `BRIEF_MODES.md` since this is a real
   interpretive choice, not the only valid reading of that formula.
3. **No persistence.** `BRIEF_MODES.md` only says an estimate "can be saved for reference,"
   not that it must be — a new table for estimate history felt like real, avoidable scope for
   a first pass, so state round-trips through hidden form fields instead. A page refresh
   loses an in-progress estimate; regenerating from the same raw text is the workaround today.
Consequences: Session C (all 4 steps) is now complete — logged in `FEEDBACK_LOG.md`.
`ASSUMPTIONS.md`'s one remaining honest gap: `PLANNING.md`'s back-scheduling
(`app/services/scheduling.py`, Session B) still reads its own hardcoded constants, not this
table — noted explicitly there, not silently left inconsistent.

## 027 — Wire app/services/scheduling.py to read live Assumption values
Date: 2026-08-27
Decision: `back_schedule()` and `build_feasibility_facts()` now take `client_review_days` /
`client_review_minimum_days` as parameters (defaulting to the existing hardcoded constants,
which stay as fallbacks for callers with no `Assumption` table to read — tests, mainly).
`generate_schedule()` fetches `client_review_days` live via
`app/services/assumptions.py`'s `get_value()` and passes it in; the `/dashboard` and
`/timeline` routes do the same for `client_review_minimum_days` before calling
`build_feasibility_facts()`. `volume_factor_for()` gained an equivalent optional `bands`
override for consistency, though nothing calls it live yet — see below. 4 new tests, 140
across the suite.
Alternatives considered: giving `back_schedule()` a `db: Session` parameter directly instead
of threading the resolved value through as a plain argument; wiring `volume_factor_for()`
to a live caller as part of this same change.
Why:
1. **`back_schedule()` stays a pure function, no `db` parameter.** Its whole design (Session
   B, decision 018) was deliberately DB-free and directly testable — dozens of existing
   tests call it standalone with synthetic `PhaseTemplate` rows. Threading a resolved
   `client_review_days: int` through as a parameter (the same pattern `volume_factor` and
   `today` already use) gets the live value in without breaking that contract; only
   `generate_schedule()`, which already has `db`, needs to know where the value comes from.
2. **`volume_factor_for()` was not wired to a live caller**, despite gaining the same
   `bands` override. Checked first: `generate_schedule()` never calls it — it passes
   `Project.volume_factor` straight through, a stored field set directly, not derived from
   an asset count anywhere in the schedule-generation path. Wiring a function with no real
   caller to live data would have been theatre; the override exists for whenever a future
   caller needs it (the same shape `estimate.py`'s own `volume_factor_for()` already uses),
   not because anything reads it today. Documented explicitly in `ASSUMPTIONS.md` rather
   than silently calling the job done.
3. **Two real bugs caught by testing this against the actual seed path, not just fixtures**,
   both fixed before landing:
   - `app/seed.py`'s `main()` called `seed_demo_schedules()` (which calls
     `generate_schedule()`) *before* `seed_assumptions()` — a fresh `--reset` would have
     crashed generating the three demo schedules, since `client_review_days` wouldn't exist
     yet. Caught by actually running `python -m app.seed --reset`, not just the test suite
     (whose fixtures seed explicitly and in whatever order each test chose, masking the
     bug). Fixed by reordering: assumptions now seed before demo schedules.
   - The `/dashboard` and `/timeline` routes fetched `client_review_minimum_days`
     unconditionally, before checking whether there were any scheduled projects at all —
     an empty dashboard or timeline would have crashed on a database with no seeded
     `Assumption` rows. Fixed by gating the fetch behind "is there at least one scheduled
     project," the same condition that already guarded whether the value would ever be used.
Consequences: `generate_schedule()` (and therefore any route that calls it, and `app/seed.py`)
now hard-depends on the `Assumption` table being seeded first — existing tests that called
`generate_schedule()` without seeding assumptions were updated to seed them
(`tests/test_scheduling.py`, `tests/test_timeline.py`, `tests/test_dashboard.py`). Verified
against a real `--reset` run, not just pytest, given the ordering bug this same change
introduced and then caught.

## 028 — Ran the full demo end to end; rewrote DEMO_SCRIPT.md to match
Date: 2026-08-27
Decision: Executed `docs/DEMO_SCRIPT.md`'s entire 8-step walkthrough against a real
`uvicorn` process from a cold `python -m app.seed --reset` (`AI_PROVIDER=mock`), driving
every click via HTTP request rather than trusting the script's claims. Every refusal
message, computed number, and outcome matched *except* two, both caused by real product
changes made after the script was originally written — not app bugs. Rewrote the script to
match current behavior and added a 9th step (Timeline and planning) covering Sessions B and
C, which had no demo coverage at all. Re-ran the complete rewritten script end to end,
sequentially, against a fresh reset to confirm every new claim too, including the step 8
assign interaction. Reset the local dev database afterward — a demo run mutates real state,
same as decision 013's reasoning for reseeding Render on every boot.
Alternatives considered: leaving the stale numbers and adding a footnote; making step 8
optional-and-separate rather than integrating it into the numbered flow; hardcoding step 8's
exact dates and figures the way earlier steps do.
Why, two real discrepancies and one design choice for the new step:
1. **Dashboard's "2 projects need intervention" is now 4.** Session A's deadline rule
   (decision 014, added after this script was written) flags two more projects
   (`Loyalty Relaunch Teaser`, `Loyalty App Push`) for running out of runway. The original
   two items are unchanged and still the ones the rest of the demo resolves — the script now
   says "4" honestly but keeps the spoken walkthrough focused on the same two, naming the
   other two only in passing.
2. **Step 6's recommendation names Alex, not Maya — because step 4 already ran.** This isn't
   a bug: `mock_insight_to_action` correctly reads live capacity, and step 4's accepted
   reassignment already pushed Maya to 100% by the time step 6 runs. The original script's
   worked example was never actually true for someone following its own steps in order.
   Fixed by updating the quoted example to Alex and adding an explicit note explaining why,
   so a presenter isn't confused if a future change shifts it again.
3. **Step 8 deliberately doesn't quote exact dates or day-counts the way steps 1–7 sometimes
   do**, even though every one of its numbers was verified live. Its content (a project's
   feasibility shortfall, its milestone dates, which phase is "behind") depends on how many
   working days have elapsed since the seed ran — genuinely time-sensitive in a way step 6's
   effort estimate or step 3's percentages aren't. Describing the pattern ("names the
   working-day shortfall and the phase most responsible") instead of the number keeps the
   script from going stale the way the original step 1 count already had.
Consequences: `docs/DEMO_SCRIPT.md` now covers all 9 screens the app has, not 6. Total run
time grew from ~6.2 minutes (the original steps already summed past the "5 Minutes" the old
title claimed) to ~7.3 minutes with step 8 included — retitled honestly, and step 8 marked as
the first thing to cut if time is short, since steps 1–7 are unchanged in substance and still
carry the whole argument on their own.

## 029 — REVIEW_02.md P0: revoke real brand names, replace with checked-clean invented ones
Date: 2026-08-31
Decision: Reversed `POSITIONING.md`'s "Demo data rules" clause that had explicitly permitted
"publicly known consumer brand names as fictional tenants" — the clause the real brand names
traced back to. Replaced Albelli/Photobox/Hofmann everywhere in the product surface (seed
data, routes, templates, tests) with invented names, each checked against a web search for
real-company collisions before use, per the review's own instruction. Used `tools/audit.py`
(new, untracked file already present in the repo when this review landed — a read-only
checker matching `REVIEW_02.md`'s sections almost 1:1) to baseline before, verify after, and
confirm the fix against a locally running instance, not just a repo grep.
Alternatives considered: using the review's own suggested replacement set
(Fotomera/Printhuis/Kadora, parent "Halden Group") and its five listed alternates
(Lumera/Bindwell/Papeterie/Momentbox/Foldhaus) as given; rewriting git history to remove the
421 historical blobs the audit tool found still containing the old names.
Why, two real findings that changed the plan:
1. **Every single name the review proposed collided with a real, active company** —
   `Printhuis` is an actual wall-art/poster shop (`printhuis.com`), the *exact* category the
   review assigned it to; `Kadora` is a real Belgian gifts company; `Halden Group` is a real
   Virginia ERP consultancy; and all five listed alternates also came back with real hits on
   a plain search (`Lumera` — a 563-employee Swedish insurtech; `Bindwell` — a funded YC
   biotech; `Momentbox` — multiple companies, one in the *exact* photo/event-services space;
   `Foldhaus` — a named Burning Man art collective; `Papeterie` — several small stationery
   shops trading under that literal name). Only `Fotomera`, the review's one suggestion for
   the NL brand, came back clean. Searched further and found four names with no meaningful
   collision — `Fotomera` (kept), `Halveth`, `Cassenvale`, and `Nordelva` (for the parent
   group) — after several more candidates (`Verlio`, `Mureno`, `Donaro`, `Ostrand`,
   `Velmara`, `Kelvara`, `Thornvale`, `Wenlow`) also came back with real hits. **A short
   invented-sounding word very often already belongs to some small, obscure, real business
   somewhere** — likely because corporate registries (UK Companies House among them) hold
   near-exhaustive dormant-name inventories. Perfect zero-hit assurance isn't achievable by
   search for a word this short; the standard actually applied was no same-or-adjacent-
   industry collision and no substantial exact-name company, which is what the review's own
   stated concern (a reviewer *recognising* the name) requires, not a literal zero anywhere.
   Final mapping: **Nordelva Group** (parent) → **Fotomera** (photo books and prints, NL),
   **Halveth** (wall art and décor, DE), **Cassenvale** (personalised gifts, FR/ES).
2. **Git history was left alone, deliberately, not overlooked.** `tools/audit.py --deep`
   found 421 historical blobs still containing the old names. Rewriting pushed history
   (`git filter-repo`/BFG, then a forced push) is exactly the kind of hard-to-reverse,
   shared-state action this project's own operating rules require checking with the owner
   before attempting — and the audit tool's own comment agrees: "History is only a problem
   if you publish the repository. If you do, consider starting a fresh repo rather than
   rewriting history." This repo is already published and deployed, so the question is real,
   not hypothetical — surfaced to the owner as a separate decision rather than acted on
   unilaterally within this fix.
Consequences: `tools/audit.py`'s `EXPECTED_BRANDS` constant updated to match the actual final
names (it still shipped with the review's original, now-abandoned suggestions) and its
comment records why they changed, so a future run of the tool checks against what's actually
true. Verified clean: full-repo grep (only `docs/REVIEW_02.md`, a historical record of the
rename, and `.claude/settings.local.json`, a local permission cache, still contain the old
names — both outside the "seed data, code, templates, or documentation" scope the review
named), `pytest` (140 passed), a fresh `--reset` seed, and `tools/audit.py --url` against a
locally running instance. Not yet re-verified against the live Render deployment or pushed —
that's a separate, explicit step given the site is public.

## 030 — REVIEW_02.md P1: two demo-schedule deadlines were the actual bug, not literal dates
Date: 2026-08-31
Decision: Widened `Spring Lookbook`'s seeded deadline from `TODAY+15` to `TODAY+35`, and
`Autumn Prints FR Push`'s from `TODAY+10` to `TODAY+47` — both still fully relative offsets,
just larger ones. Verified against `app/services/scheduling.py`'s own feasibility check
(`build_feasibility_facts`) rather than eyeballing the dashboard: `Spring Lookbook` (Stills)
and `Mother's Day Static Set` (Social) now come back fully feasible; `Autumn Prints FR Push`
(Film) comes back exactly 2 working days behind — inside the review's "no more than 2" bar,
not zeroed out.
Alternatives considered: auditing every date in `seed.py` for hardcoding, since that's the
literal fix `REVIEW_02.md`'s "Fix" section describes; dropping Film from the three
demo-scheduled projects entirely, matching how Event already has no demo instance, so every
demonstrated schedule is comfortably feasible with no exception to carve out.
Why:
1. **Every date in `seed.py` was already a relative offset — `tools/audit.py`'s own P1 check
   already passed before this fix, and still does.** The "29 working days behind" symptom
   `REVIEW_02.md` reports has nothing to do with hardcoded dates; it's decision 020's
   deliberate choice to pair `Autumn Prints FR Push`'s short seeded deadline with the Film
   template (needing ~35 working days ≈ 7 weeks), specifically to demonstrate the "Behind"
   badge and feasibility panel. That pairing is badly infeasible on *every single reseed,
   forever* — not a one-time drift, a permanent structural mismatch — which is exactly what
   reads as broken on a public site rather than as a deliberate teaching moment. The owner's
   direct testing has now overruled that Session B call; documenting the reversal here rather
   than treating it as an oversight.
2. **Kept a small, real shortfall (2 working days) instead of making everything feasible.**
   Dropping Film from the demo set entirely would have been the simpler fix and was
   seriously considered — but it would silently break `DEMO_SCRIPT.md` step 8, which
   specifically narrates a Behind badge, a feasibility panel with a real shortfall, and
   conflict-outlined phase bars. A shortfall of "2 working days" is a plausible, honest
   thing for a real schedule to show; "29 working days" was never plausible, and the fix for
   an implausible number is a plausible one, not zero. `DEMO_SCRIPT.md` already avoided
   quoting exact figures for this reason (`DECISIONS.md` 028) so it stays accurate without
   any further edit.
3. **Both deadline changes are safe**, checked directly against the code: every `Assignment`
   and `Localisation` row in `seed.py` uses its own independent `TODAY ± offset` expression,
   never derived from `Project.deadline`. Neither `Spring Lookbook` nor `Autumn Prints FR
   Push`'s deadline is load-bearing for any of `DEMO_DATA.md`'s five required conflicts —
   confirmed by reading, not assumed: Maya's headroom (conflict 2) comes from a separately-
   dated `Assignment` row; the FR localisation bottleneck (conflict 4) comes from a
   separately-dated `Localisation.due_date`, explicitly commented `"the deliberate
   bottleneck, unchanged"` in the seed code, and genuinely left unchanged here.
Consequences: the wider spread also happens to help `REVIEW_02.md`'s general "deadlines
spread across the coming six weeks" verify bar — the seeded deadlines previously maxed out at
24 days out; they now reach 47. Four projects (not the stated "two or three") fall within 7
days of today, but three of the four coincidentally land on the exact same date this seed run
(today's "next Friday" and a hardcoded `TODAY+4` both resolve to the same day) — close enough
in spirit to the review's target that it wasn't worth trimming further and risking the
required-conflict framing. `Deliverable`/`Localisation` rows tied to `Spring Lookbook` and
`Autumn Prints FR Push` still show their original literal-relative due dates (e.g.
`TODAY+15`), now earlier than their project's new deadline — left as is; a deliverable due
ahead of a project's overall delivery date is normal, not a bug.

## 031 — REVIEW_02.md P7 copy item, done early: renamed "Mother's Day Static Set"
Date: 2026-08-31
Decision: Renamed the seeded project `"Mother's Day Static Set"` to `"Yearly Mother's Day
Assets"` in `app/seed.py` (project name, the P7 localisation comment, and the
`DEMO_SCHEDULE_PROJECTS` key/comment). The `campaign` field (`"Mothers Day"`) and the
`brief_raw` text (which describes the brief content, not the project's own timing) are
unchanged.
Why: the owner asked directly — checking the live app — whether this project's schedule was
tied to the real Mother's Day, which is exactly `REVIEW_02.md` P7's own flagged item: the
project's deadline is `TODAY + timedelta(days=24)`, so on every reseed it lands roughly 3-4
weeks out from whenever the seed happens to run, never actually near the real holiday (March
in the UK, May across most of the rest of Europe). Confirmed on this run: deadline resolves
to 2026-09-24, nowhere near either. Moving the date wouldn't fix this — no fixed offset from
"today" reliably lands near a specific calendar holiday — so the review's other suggested
fix, renaming, is the only one that actually holds under a stale-never demo reseed. The
owner's own suggested name ("Yearly Mother Day assets") is used, cleaned up to match this
project's existing naming style (title case, correct possessive) and the pattern already set
by `"Retouch Guidelines Refresh"` — framing it as ongoing/evergreen seasonal-asset
production rather than a project scheduled to land on the holiday itself.
Consequences: taken out of P7 order, ahead of P2-P6, because it was a direct, specific
question about live app behaviour rather than a request to work the review section by
section — the rest of P7's copy items are still pending. Verified: full-repo grep (no other
references to the old name outside this decision entry and `docs/REVIEW_02.md`, both
historical), `pytest` (140 passed), a fresh `--reset` seed, and `build_feasibility_facts`
re-run directly against the renamed project (still fully feasible, unaffected — the rename
touches display text only, not scheduling math).

## 032 — REVIEW_02.md P2: one definition of "how loaded is this person," enforced not just displayed
Date: 2026-08-31
Decision: Four changes to `app/services/capacity.py` and its callers:
1. Added `peak_allocation_pct(assignments, from_date)` — the worst allocation across a
   person's timeline from `from_date` onward, not a single-date snapshot. `person_capacity()`
   (and therefore `all_person_capacities()`, used by the Resources table, the dashboard's
   overloaded count, and the Creative Intelligence screen) now calls this instead of the old
   `current_allocation_pct`, which only looked at exactly one day.
2. Consolidated the window-bounded peak calculation that `app/services/assignment.py`
   (`phase_candidates()`) had reimplemented locally (`_max_allocation_in_window`) into
   `capacity.py`'s `max_allocation_pct(assignments, start, end=None)` — `peak_allocation_pct`
   is just this with `end=None`. Also added `available_pct()` and `aggregate_utilisation_pct()`
   so the trivial `capacity - allocated` subtraction and the dashboard's team-wide percentage
   aren't each re-derived at their call sites. Deleted `current_allocation_pct` — once
   `person_capacity()` moved off it, nothing else called it.
3. **`assign_phase()` now enforces the same availability rule `phase_candidates()` uses to
   populate its own dropdown**, instead of allowing a direct call to bypass it. This reverses
   part of decision 020, which deliberately let an "override" stack a person past
   `phase_candidates()`'s filter on the theory that `capacity.py`'s conflict detection would
   catch it as "the intended integration, not a gap." It doesn't — nothing ever re-checked
   availability after the first assignment, so repeated or replayed assigns could stack a
   person's allocation with no ceiling. This is the mechanism `REVIEW_02.md` describes
   producing "540% against 80% contracted": not one bug in one place, but the combination of
   a snapshot-only status figure (fixed by change 1) and an unenforced availability filter
   (fixed here).
4. Labelled the accepted-recommendation figures on `/resources` "At time of recommendation"
   (`app/templates/resources.html`) — those numbers are correctly frozen at
   `payload.impact.*_new_allocation` from when the recommendation was generated (P2 fix item
   4 says this is correct and should stay), but nothing signalled they weren't live, which is
   how they read as one more contradictory number next to the table and the conflict panel.
Alternatives considered: leaving `assign_phase()`'s override in place and instead capping
`allocation_pct` at display time (e.g. clamping anything over some ceiling) — rejected because
it would hide a real data problem behind a fake number, the opposite of what P1 and P2 both
already established this session (a plausible real shortfall beats a suppressed one).
Why: `REVIEW_02.md`'s fix item 1 ("there should be one place, delete the others, route
through capacity.py") was already mostly true — `dashboard.py`, `resources.py`, and
`assignment.py` all called into `capacity.py`'s primitives rather than reimplementing
allocation math from scratch. The actual bug was semantic, not structural: two call sites
used the *same* primitive with *different window definitions* (a single date vs. a full
timeline), so they could legitimately disagree about the same person on the same day. Fix
item 3 ("define the window explicitly and use it consistently") is the real fix; the
mechanical "one file" consolidation (changes 2 and 4) was worth doing anyway since it was
already most of the way there and `tools/audit.py`'s own heuristic flagged the remaining
inline subtractions.
Consequences: a person who is free today but double-booked starting next week now shows as
tight/overloaded immediately, not only once that week arrives — this is a behaviour change,
not just a display fix, and makes the Resources table slightly more pessimistic-looking on
days when no one's *current* segment is over capacity but a future one is. That is the
correct trade for this app: `DEMO_DATA.md`'s conflicts are meant to be visible, not deferred.
`assign_phase()` refusing an over-capacity assignment also changes
`test_overload_created_by_a_phase_assignment_is_visible_to_get_conflicts` (renamed
`test_assign_phase_refuses_when_not_enough_spare_capacity`) — it asserted the old override
behaviour directly, so it had to change with it, not just tolerate it. Added
`test_allocation_identical_whichever_service_path_computes_it` per `REVIEW_02.md`'s own
verify bar. Verified: `pytest` (142 passed, up from 140 — two new tests, one rewritten), a
fresh `--reset` seed, and `tools/audit.py --url` against a locally running instance — the P2
"Over-capacity summary reads '1 of 8' with no contradiction" check now passes; the tool's
own "different percentages across pages" and "9999%" warnings on `/timeline` and
`/intelligence` are false positives (a phase-candidate's window-specific "% free" is a
different, correctly-labelled metric from a person's overall status, and the "9999%" is the
regex matching the tail of an unrelated long decimal, e.g. `1.5499999999999998%` — a real but
separate float-formatting issue, not a capacity bug, left for a P7 copy pass). `tools/audit.py`
(no `--url`) still flags one inline `aggregate_utilisation_pct(capacities)` call as "arithmetic
outside capacity.py" — a false positive from the same coarse regex matching `utilisation\s*=`
against the call site, not a computation.

## 033 — Rounded float-arithmetic seed values on Creative Intelligence
Date: 2026-08-31
Decision: `app/seed.py`'s DE lifestyle/product-only `CreativeInsight` rows computed
`engagement_rate` and `conversion_rate` as `4.5 + i * 0.2`-style float arithmetic with no
rounding, which occasionally lands on values like `1.5499999999999998` due to ordinary binary
float imprecision — stored as-is, then rendered raw in `/intelligence`'s per-row table
(`{{ i.engagement_rate }}%`, no template-side rounding). Wrapped both in `round(x, 2)` at the
point of computation. Noticed as a side effect of `tools/audit.py --url`'s P2 pass flagging
"9999%" on `/intelligence` — a false positive for the capacity check (it was matching the tail
of the long decimal, not an actual percentage), but a real, separate display bug once traced.
Why fixed at the source (seed.py) rather than in the template: `app/services/insight.py`'s
`compute_market_comparisons()` already rounds its own aggregates correctly — only the seed
data feeding the raw table was unrounded, and nothing else in the app writes a
`CreativeInsight` row (seed-only in V1 scope), so there's no other path that could reintroduce
this.
Consequences: none beyond cleaner numbers — no test asserted the old unrounded values.
Verified: `pytest` (142 passed), a fresh `--reset` seed with all 24 rows checked directly
(`round(...)` output confirmed short, e.g. `1.55` not `1.5499999999999998`).

## 034 — REVIEW_02.md P3: write-through and recompute
Date: 2026-08-31
Decision: Investigated each of the five reported symptoms directly (a repro script per
symptom, run against the actual routes via `TestClient`, not just reasoning about the code)
before changing anything — most of this codebase already computes everything at display
time from live queries (no cache, no stored-and-synced figure anywhere), so the fix was
narrower than "add a write-through layer": four real, specific gaps, plus one symptom that
didn't reproduce at all.
1. **"Accepting a resource recommendation does not update capacity figures elsewhere"** —
   the Assignment row moves correctly and capacity recomputes correctly (proved directly:
   reassigning Alex's project to Maya via `/recommendations/{id}/accept` updated both
   people's allocation on the next query, no caching involved). The actual bug is
   `ProjectPhase.assigned_person_id` — a denormalized field `assign_phase()` sets for
   Timeline's own display, alongside the Assignment row. `_apply_resource_reallocation`
   only touched the Assignment row, so a recommendation that reassigns a *phase-derived*
   assignment leaves Timeline showing the person the work was just moved away from,
   forever. Fixed in `app/routes/recommendations.py`: `computed_facts_json` now carries the
   exact `assignment_id` captured when `_build_conflict_facts()` (resources.py) built the
   recommendation, used as the primary lookup instead of an ambiguous `(project_id,
   person_id)` scan — a person can hold more than one Assignment on the same project (a
   whole-project one plus a phase-derived one; more so now that change 5 below adds a second
   way to create one), and only the ID disambiguates which is being moved. When the moved
   row has a `project_phase_id`, the matching `ProjectPhase.assigned_person_id` is now
   updated in the same transaction.
2. **"Changing a value in the Assumptions library does not reschedule affected projects"**
   — real. Checked every `Assumption` key against every place that reads it
   (`grep -rn "get_value(db"`): `client_review_days` is the *only* one `generate_schedule()`
   consumes and persists as `ProjectPhase` rows — every other scheduling-tagged assumption
   (`client_review_minimum_days`, lead times, volume scaling, confidence bands) is already
   read live at display time by `build_feasibility_facts()`/`compute_estimate()`, so there
   was nothing stale for those. Fixed by having `/assumptions/{id}/update` and
   `/assumptions/reset` call `generate_schedule()` again for every project that currently
   has a schedule, but only when the changed key is `client_review_days` — regenerating for
   an assumption that can't change the dates would just destroy a producer's manual phase
   assignments for no reason. This made a second, previously latent bug reachable: nothing
   in `app/models` declares a relationship or cascade between `ProjectPhase` and
   `Assignment`, so `generate_schedule()` deleting the old phases orphaned any Assignment row
   `assign_phase()` had created against them — a dangling row with a real person, real dates,
   still counting toward that person's capacity forever, against a phase that no longer
   exists on any schedule. Fixed in the same function: delete those Assignment rows in the
   same transaction as the phases they belonged to.
3. **"Assigning a translator on the localisation page does nothing"** — literally true:
   `/localisation` had no assign control at all, only a read-only grid (the working
   `/localisation/{id}/assign` route existed, but only `/projects/{id}`'s page had a form
   that posted to it). Added the same inline assign form to each grid cell. Since this page
   is the one place in the app a producer would filter by market/stage first, redirecting
   away to a project page after every assign would undo that filtering — added an optional
   `return_to` field (validated against a `/localisation` or `/projects/` prefix, never an
   arbitrary posted URL) so the action redirects back to wherever it was submitted from;
   `/projects/{id}`'s existing form posts no such field and keeps its original behaviour.
4. **"Assigning a resource on the project page does nothing"** — also literally true: the
   Assignments section on `/projects/{id}` was a read-only table with no write path
   whatsoever. Added `POST /projects/{project_id}/assign` — a manual whole-project
   assignment (`project_phase_id` stays `None`, distinct from a phase-derived one), with the
   same eligibility rule (`resources.py`'s producer/translator exclusion) and the same
   spare-capacity enforcement decision 032 added to `assign_phase()` — a manual assign can't
   stack a person past a plausible ceiling any more than a phase assign can. Replaces rather
   than stacks a second row for the same (person, project) pair, matching `assign_phase()`'s
   own convention.
5. **"Pipeline status changes do not update the dashboard"** — did not reproduce. Traced
   directly: `change_status()` commits `project.status` and every dashboard figure is
   recomputed from a fresh query on the next page load, proved with a repro script that
   changed status via the actual route and re-fetched `/dashboard` immediately after. No fix
   applied — noted here so a future session doesn't re-investigate the same claim from
   scratch.
6. **"Everything appears unassigned after actions that should have assigned it"** — not
   chased as a separate bug; change 1's `ProjectPhase.assigned_person_id` staleness is a
   direct match (Timeline reads exactly that field to render "who's assigned") and is now
   fixed by the same change.
Deliberately not fixed here: the fix table's "assign translator -> ... the translator's
allocation" — this data model has no Assignment row for a translator at all (Localisation's
`translator_id` is a separate FK), so there is no "allocation" figure to update, only one to
build. `REVIEW_02.md` P5.5 explicitly scopes "external talent pool with lead time/cost" as
its own item — building a partial version of that here to satisfy one fix-table cell would
mean redoing it properly in P5.5 anyway.
Verified: `pytest` (156 passed, up from 144 — 12 new tests, one per fixed gap plus edge
cases: disambiguated reassignment, phase sync, orphan cleanup on regenerate, live reschedule
via the actual route, localisation-page assign with `return_to` handling including an unsafe-
URL guard, manual project assign including the capacity guard and replace-not-stack). Every
fix also verified against a real running server, not just unit tests: reassignment moving an
Assignment and syncing its phase, an assumption edit changing a stored phase's duration
through the actual route, a translator assign updating both the per-market summary and (by
inspection of `get_localisation_risks`) the localisation risk flag live, and a manual project
assign changing a person's `/resources` allocation figure live. `tools/audit.py --url`
re-run clean of anything new — the remaining findings (P5.1 project links, P5.2 timeline
coverage, P7 copy) belong to later sections.

## 035 — REVIEW_02.md P4: insight lifecycle state, without a new stored status column
Date: 2026-08-31
Decision: Extended round 1's "one pending recommendation per conflict" rule
(`resources.py`) to Creative Intelligence, and gave each market's lifestyle-vs-product
insight the four-state lifecycle the review asks for (`new` / `recommendation_pending` /
`actioned` / `dismissed`) — but stored almost none of it. Added exactly one column,
`CreativeInsight.dismissed_reason` (nullable text). Everything else is computed at display
time in `app/services/insight.py::compute_insight_status(db, market)`:
`recommendation_pending` and `actioned` are derived by checking whether a pending or
accepted `production_action` Recommendation exists whose `computed_facts_json["market"]`
matches; only `dismissed` has no Recommendation to derive from, so it's the one thing that
needs real storage.
`/intelligence/recommend` now mirrors `resources.py`'s dedup exactly: build the facts,
find an existing pending recommendation for the same market, return "nothing has changed
since it was generated" if the facts match, replace it if they don't. Blocks outright only
for `actioned`/`dismissed` (terminal) — a pending recommendation does *not* block a repeat
request, matching `resources.py`'s own precedent (its "Get AI recommendation" button is
never hidden while a conflict has a pending recommendation) and the review's literal verify
text, which only asks for the control to disappear *after* accepting, not while pending.
New `POST /intelligence/{market}/dismiss` (reason required, a blank one refused) sets
`dismissed_reason` identically across every `CreativeInsight` row in that market's
lifestyle/product_only group — dismissal is a property of the market-level opportunity, not
of one raw performance row, so grouping rather than a per-row flag matches what the review
actually means by "insight."
Alternatives considered: an `InsightStatus` enum column on `CreativeInsight`, storing
`new`/`recommendation_pending`/`actioned` explicitly. Rejected — `REVIEW_02.md` P3's own
rule, applied one section later: "nothing derived may be stored where it can drift."
`recommendation_pending`/`actioned` are both already fully knowable from `Recommendation`
rows that exist for exactly this reason; storing them a second time would just be a second
place for the two to disagree, the same class of bug P2 and P3 both just finished removing.
A separate `Opportunity`/`InsightGroup` table was also considered, to give the market-level
concept its own identity instead of denormalizing `dismissed_reason` across several rows —
rejected as more schema than this demo's scale needs; `ProjectPhase.required_roles`
(decision noted in `app/services/scheduling.py`) already sets the precedent that a small,
deliberate denormalization is fine here when the alternative is a new table for one field.
Consequences: rejecting a pending recommendation reverts the insight straight back to `new`
(no separate "insight was rejected" state — the review's four states don't include one, and
a producer can simply request again). `compute_insight_status` does one extra query per
displayed market comparison (small, single digits in this demo's data) rather than joining
in SQL, consistent with how every other cross-entity check in this app already works
(`get_conflicts`, `build_attention_snapshot`) — Python filtering over a full table, not a
query optimised for a scale this app doesn't have.
Verified: `pytest` (166 passed, up from 156 — 10 new tests: dedup across three repeated
requests creating one record, phase-appropriate blocking, reject reverting to new, dismiss
requiring a non-blank reason and applying across a market's full row group, dismiss of an
unknown market returning false rather than raising). Also verified against a real running
server end to end: three POSTs to `/intelligence/recommend` for the same market created one
`Recommendation`; accepting showed "Actioned" with the outcome text and a working project
link and removed the request control; a fresh request afterward was refused with no new row
created; dismissing a different market set its badge and blocked further requests on that
market specifically, leaving others untouched. `tools/audit.py` clean of anything new.

## 036 — REVIEW_02.md P5.1: one shared project-reference partial
Date: 2026-08-31
Decision: Added `app/templates/partials/_project_ref.html` — a single Jinja macro,
`project_ref(project_id, project_name, css_class="hover:underline")`, rendering the one
`<a href="/projects/{id}">{name}</a>` pattern every other project link in the app already
used ad hoc. Imported it in every template that names a project — `_board.html`,
`dashboard.html`, `timeline.html`, `localisation.html`, `resources.html`,
`intelligence.html`, `brief.html` — and used it at all 14 occurrences the survey found,
including the 6 already correctly wrapped in a hand-written `<a>` (converted for
consistency, not because they were broken) and the 8 that weren't linked at all.
Three of the 8 needed more than swapping in the macro:
1. **Dashboard's Schedule card** (`alert.project.name`) sat inside the card's own outer
   `<a href="/timeline">` — nesting a second anchor inside it is invalid HTML and
   unpredictable in browsers. Restructured: the card is a `<div>` now, each alert gets its
   own `project_ref` link, and a `View timeline →` link at the bottom matches the pattern
   the other two dashboard cards (Team capacity, Localisation) already use.
2. **Timeline's row header** (`row.project.name`) was the *text inside* the accordion
   toggle `<button>` — same nested-interactive-element problem, `<a>` inside `<button>` is
   invalid. Split the disclosure arrow (now its own small unlabelled button) from the
   project name (now a real link) — this was arguably a UX bug on its own: clicking the
   name previously only toggled the row, it never went anywhere.
3. **Resources' "Current assignments" column** had no id in scope *at all* — the route
   (`app/routes/resources.py`) pre-flattened each person's assignments into a joined string
   of names before the template ever saw them. Changed `current_assignments` from
   `dict[int, list[str]]` to `dict[int, list[int]]` (project ids), letting the template look
   names back up via the `projects_by_id` already in context.
Also added a project link to Dashboard's "Needs attention" list, which named a project only
inside AI-generated prose (`item.statement`) with `item.project_id` sitting unused in the
`AttentionItem` schema — added `projects_by_id` to the dashboard route's context and a
`project_ref` link ahead of the existing "→ Resources/Timeline/…" screen link, so the
specific project is reachable, not just the screen that explains it.
Alternatives considered: a Jinja custom filter or a Python helper function registered as a
Jinja global, instead of a macro file. A macro needing an explicit `{% from %} import` at
the top of every template was slightly more typing than a global, but keeps every
template's dependencies visible in its own first two lines rather than implicit — matches
how this app already prefers explicit imports over ambient globals everywhere else in the
Python code.
Consequences: `resources.html`'s recommendation-outcome note (`rec.outcome_note` for an
accepted resource reallocation) was deliberately left without its own link — that
recommendation's card header, immediately above it, already links the same project; a
second identical link right below would be noise, not a missing reference.
`tools/audit.py --url`'s P5.1 check still flags `/brief` and `/intelligence` on a
fresh reseed — verified by hand this is a crawl-state artifact, not a real gap: `/brief`
only shows a created-project link *after* a real create-project POST (nothing to link on
the bare form), and `/intelligence` only shows a project link once a `production_action`
recommendation has actually been accepted into a project (nothing exists yet on an unused
instance). Manually drove both flows against a running server and confirmed the link
appears exactly when there's something to link to.
Verified: `pytest` (170 passed, up from 166 — 4 new tests covering the three route-level
behaviour changes above, since the other 11 sites were template-only swaps with no new
logic to test). Every rendered page (`dashboard`, `resources`, `timeline`, `localisation`,
`intelligence`, `pipeline`) checked directly against a running server.

## 037 — REVIEW_02.md P5.2: Timeline shows every project it safely can
Date: 2026-08-31
Decision: `/timeline`'s route already showed every project with a generated schedule — the
"3 of 16" gap was entirely that only 3 of the 12 seeded projects had ever been given a
`project_type_id` at all, decision 021's own scope limit for Session B. Extended
`DEMO_SCHEDULE_PROJECTS` in `app/seed.py` from 3 to 6: added Photobook Bundle Homepage
Banner (Stills), Calendar Season Kickoff (Social), and Gift Card Email Series (Social),
covering every seeded project at status Ready through Creative Review. Also added `Planned`
styling to `/timeline`'s rows and bars (lighter, outlined) for Ready-status projects, per
the review's explicit ask to distinguish planned from committed work.
Considered and rejected extending to all 10 non-Brief projects (literal "every project from
Ready onwards"):
1. **Winter Campaign Refresh and Loyalty Relaunch Teaser stay excluded.** Both have
   deliberately tight deadlines that `DEMO_SCRIPT.md` narrates by name — Winter Campaign
   Refresh's Friday-this-week date drives `DEMO_DATA.md`'s capacity-overload conflict;
   Loyalty Relaunch Teaser sits inside `attention.py`'s 7-working-day deadline-proximity
   window, narrated in `DEMO_SCRIPT.md` step 1. Tried widening Loyalty Relaunch Teaser's
   deadline first (to bring its schedule shortfall under `tools/audit.py`'s own 5-day
   plausibility bar) — it worked for feasibility but pushed the deadline past that 7-working-
   day cutoff, silently deleting it from the dashboard's "needs attention" narrative. Reverted
   rather than trade one review requirement for another. Scheduling either against the Social
   template computes a genuine double-digit-day shortfall; that's an honest consequence of a
   deadline this tight, not a bug to hide, but showing it would reproduce the exact
   implausible-number pattern decisions 030 and 032 already removed elsewhere in this app.
2. **Canvas Prints Paid Display (Approved) and New Year Cards Social Set (Delivered) stay
   excluded.** Both are functionally finished. A backward schedule computed from today
   against a deadline already in the past, or a few days out, for work that's already
   done, doesn't produce a plan anyone needs — it produces a large, meaningless "behind
   schedule" number for a project nobody is still staffing. Same reasoning as item 1.
3. **Loyalty App Push and Retouch Guidelines Refresh stay excluded** — both still at status
   Brief, and the review's own instruction is "from Ready onwards."
For the three added, widened two deadlines slightly (Photobook Bundle Homepage Banner and
Calendar Season Kickoff needed no change; Gift Card Email Series moved from `TODAY+6` to
`TODAY+13`) to bring their shortfalls to exactly `tools/audit.py`'s 5-working-day ceiling —
checked each against `DEMO_SCRIPT.md` and `DEMO_DATA.md` by name first, confirmed none of
the three is narratively load-bearing the way the two excluded ones are.
Consequences: `seed_demo_schedules()`'s console output now reports the actual count
(`len(DEMO_SCHEDULE_PROJECTS)`) instead of a hardcoded "3 projects" string, so this doesn't
drift out of sync again the next time the set changes.
Verified: `pytest` (171 passed, up from 170 — one new test asserting a Ready-status project
renders exactly one "Planned" badge and a committed one renders none). Every added project's
`build_feasibility_facts()` shortfall re-checked directly (all ≤5 working days, two fully
feasible). `tools/audit.py --url` P5.2 check now passes ("Timeline shows 6 projects against
12 on the pipeline"); P1's "no project more than 5 working days behind" check still passes
too, confirming the widened deadlines didn't reintroduce that class of problem.

## 038 — REVIEW_02.md P5.3: sequence is free, the readiness gate is scoped by tempo
Date: 2026-08-31
Decision: Two changes, kept deliberately separate. `validate_transition()`
(`app/routes/pipeline.py`) no longer refuses a forward skip — any status to any status is
allowed now (only "already in this status" is still refused). `check_readiness_gate()` is
unchanged in *what* it checks, but is now skipped entirely when the project's new
`production_tempo` field is `fast_track`. Added `ProductionTempo` (`fast_track` / `standard`
/ `full_production`, default `standard`) to `Project`, a `POST /pipeline/{id}/tempo` route
and board control mirroring the existing priority control, and a "Fast-track" badge on the
pipeline card. Also enriched the gate's refusal message to name the actual missing fields
(`BriefAnalysis.missing_fields_json`, already computed by the Brief Assistant) instead of
only the aggregate readiness score — the review's fix text asks for the reason to name "what
is missing and what it blocks," and the score alone doesn't.
`standard` and `full_production` get identical gate behaviour — the review only describes
fast_track behaving differently ("A full-production project entering production without
format specifications is still refused" reads as *preserving* the existing check, not adding
a second, stricter one) and inventing an undescribed distinction between the other two tiers
felt like the wrong kind of judgement call to make silently.
No seeded project's `production_tempo` was set to anything but the `standard` default —
none of the 12 is actually "a market re-version, a copy swap, a resize, or an artwork
resend" in its brief content, and relabelling one that isn't would be less honest than
leaving the field at its accurate default. The new `/pipeline/{id}/tempo` control makes the
feature demonstrable live instead — setting a project to fast-track and skipping it straight
to Creative Review past an unmet readiness gate is a real, working action a demo can show
directly, not a pre-baked example.
Consequences: `test_skipping_a_stage_forward_is_refused_with_a_reason` inverted to
`test_skipping_a_stage_forward_is_allowed` — it asserted exactly the sequential-only
behaviour this section removes.
Verified: `pytest` (176 passed, up from 171 — 6 new/changed tests: free forward movement,
fast-track skipping the gate, full_production still gated identically to standard, the new
tempo route persisting and rejecting an invalid value, the missing-fields text appearing in
a refusal). Verified against a running server: `POST /pipeline/4/status` moved a Brief-status
project straight to Creative Review in one call; `POST /pipeline/4/tempo` set it fast-track
and the board rendered the badge. `tools/audit.py` clean of anything new.

## 039 — REVIEW_02.md P5.4: four new lifecycle states, scoped narrowly
Date: 2026-08-31
Decision: Added `waiting_on_client`, `on_hold`, `cancelled`, `archived` to `ProjectStatus`,
plus `Project.status_reason` (the most recent reason given, not a full history — same
single-field convention as `Recommendation.outcome_note`). `waiting_on_client` sits in the
main pipeline sequence right after Creative Review, the split the review asks for. The other
three are exception states, appended after Delivered rather than woven into the sequence,
and treated specially in two places:
1. `check_readiness_gate()` exempts them outright — pausing or cancelling a project must
   always be possible regardless of brief readiness, unlike `waiting_on_client`, which stays
   fully gated (getting there means real production already started, the same bar as any
   other post-Ready stage).
2. Dashboard's `active_projects` now excludes them alongside `delivered` — a project on hold
   or cancelled isn't work in flight, and counting it as active would misstate how much is
   actually moving. `waiting_on_client` stays counted as active; it's real, ongoing work,
   just externally paused rather than internally stuck.
"Status changes to hold, cancel, or backwards capture a reason": added a `status_reason`
form field to the same status-change form (not a separate one — a separate form invites
submitting a reason with no status change to attach it to). Required only for a move to
`on_hold`/`cancelled`, or a move to an earlier point in `PIPELINE_SEQUENCE` — a new list
that's `STATUS_ORDER` minus the three exception states, since "backward" is only a
meaningful question for points that were ever on the sequence. `validate_transition()` still
allows the move as an ordinary free transition (per decision 038); the reason requirement is
a second, independent check in `change_status()`, not a rule `validate_transition()` itself
enforces.
Deliberately not built here: the review's stated payoff ("it makes at-risk logic
considerably smarter — work blocked on a client is not a capacity problem") and its own
P6.3 heading ("derive the Blocked tile from these states") both point to the actual
dashboard-tile rewiring belonging to P6.3, not here. Checked first that nothing already
mis-triages `waiting_on_client` as capacity-driven: `attention.py`'s deadline-proximity rule
only fires for `EARLY_STATUSES = (brief, ready, assigned)`, which `waiting_on_client` was
never part of, and the capacity-conflict rule is driven entirely by `Assignment`/`Person`
data, never by `Project.status` — so the new status doesn't accidentally get miscategorised
today, it just isn't yet POSITIVELY surfaced as its own "blocked, and it's not us" signal.
That positive surfacing is P6.3's job.
No seeded project's status was changed to any of the four new values — DEMO_DATA.md's
distribution and DEMO_SCRIPT.md's narrative are both built around the existing seven-stage
spread, and none of the 12 is actually on hold, cancelled, waiting on a client, or archived
in its brief content. The new board control (`POST /pipeline/{id}/status` with a reason)
makes every new state demonstrable live instead.
Verified: `pytest` (181 passed, up from 176 — 5 new/changed tests: backward move refused
without a reason and allowed with one and stored, hold refused without a reason, cancel with
a reason allowed and stored, all three exception states reachable from a low-readiness
project that would otherwise be blocked, `waiting_on_client` still gated identically to any
other post-Ready stage). Verified against a running server: all 11 columns render on
`/pipeline`; a hold with a reason persisted and displayed on the card; `/dashboard` still
renders with `on_hold` and `waiting_on_client` projects present. `tools/audit.py` clean of
anything new.
