# Changelog

All notable changes to this project, by build phase. See `docs/DECISIONS.md` for the
reasoning behind individual decisions.

## Phase 8 — Documentation and demo

- Added `README.md`: purpose, architecture, install, environment variables, database setup,
  running locally, AI configuration, testing, known limitations.
- Completed `docs/DEMO_SCRIPT.md` with real project names, numbers and rationale text
  verified against the actual running app and seed data.
- Added this changelog.

## Phase 7 — Tests

- Added tests for the three areas not yet covered: project creation from a brief (through
  the real routes via `TestClient`), the recommendation accept/reject cycle, and the
  localisation risk rule.
- Added `tests/conftest.py` with a shared `TestClient` fixture.
- Fixed a `datetime.utcnow()` deprecation warning.
- 33 tests passing.

## Phase 6 — UX polish

- Fixed a real gap: the Resources and Intelligence "recommend" actions silently did nothing
  when the AI call returned `None`. Both now show a fallback banner, completing the
  empty/loading/error trio on every AI panel.
- Added a loading indicator on the three AI-triggering forms.
- Replaced two stale "coming in Phase 4" placeholders on the project detail page with real
  content: the brief extraction/readiness score, and the recommendation history.
- Added the "Demo data" label to Pipeline and Dashboard, per `docs/POSITIONING.md`.

## Phase 5 — Localisation

- Project detail's localisation table is interactive: assign a translator, advance the
  status ladder (Not started → In translation → In review → QA → Approved).
- Wired `check_localisation_risk` (AI-narrated) into the project detail Risk assessment
  panel, rebuilt to operate at the project level across multiple target markets.
- Pipeline cards and the risk panel share one live-computed signal
  (`app/services/attention.py`) rather than a stored `Project.risk_level` column.

## Phase 4 — AI layer

- All five AI functions from `docs/AI_WORKFLOWS.md` wired end to end: `analyse_brief`,
  `recommend_resource`, `insight_to_action`, `assess_portfolio_attention`,
  `check_localisation_risk`.
- Mock implementations read real computed facts rather than returning canned text — the app
  runs fully with `AI_PROVIDER=mock` and no API key.
- Brief Assistant: extraction, deterministic readiness rubric, create-project flow. Pipeline
  enforces the readiness gate (can't move past Ready below the configured threshold).
- Resource recommendation + Accept/Reject: the core "AI recommends, humans decide" loop.
- Creative Intelligence: deterministic CTR-gap comparison per market; accepting a production
  recommendation creates a Project, Deliverable, Assignment and Localisation row in one
  transaction.
- Dashboard attention panel: AI-narrated snapshot with an invention guard.
- Found and fixed real bugs along the way: false-positive market detection from substring
  matching, a hedged audience statement scoring as confirmed, a mismatched channel/deliverable
  vocabulary, and production recommendations being assignable to producers instead of
  designers.

## Phase 3 — Core workflow

- Deterministic capacity math (`app/services/capacity.py`): allocation timelines, overlap
  detection, conflict reporting — 11 unit tests.
- Resources, Pipeline, Project detail and Dashboard screens render real seed data.
- Pipeline status changes persist and enforce the stage-ladder rule: skipping stages forward
  is refused with a reason; single-step and backward moves succeed.

## Phase 2 — Skeleton

- FastAPI app boots with five screens, health check, and SQLAlchemy models for every entity
  in `docs/DATA_MODEL.md`.
- Seed script reproduces all five required conflicts from `docs/DEMO_DATA.md`.
- Localisation scaled to 20 rows across most projects to reflect realistic multi-market
  campaign rollout.

## Phase 1 — Architecture

- Stack confirmed (Option A: FastAPI, Jinja2, HTMX, SQLite), folder structure, model sketch,
  route list, template inventory, AI service interfaces, risk list. No application code.
