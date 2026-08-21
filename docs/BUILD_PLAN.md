# Build Plan — One Day to V1

Total budget: roughly 8 focused hours. The times below are targets, not estimates of your
ability — they exist so you can tell when to cut scope rather than push the deadline.

**The rule that protects the day:** finish each phase's exit criteria before starting the
next. A half-finished dashboard plus a half-finished AI layer is worth nothing at 6pm. A
finished dashboard and no AI layer is still demonstrable.

Suggested clock, starting 09:00:

| Phase | Target | Ends by |
|---|---|---|
| 0 — Setup | 30 min | 09:30 |
| 1 — Architecture | 30 min | 10:00 |
| 2 — Skeleton | 60 min | 11:00 |
| 3 — Core workflow | 150 min | 14:00 (incl. break) |
| 4 — AI layer | 105 min | 15:45 |
| 5 — Localisation | 45 min | 16:30 |
| 6 — UX polish | 45 min | 17:15 |
| 7 — Tests | 40 min | 17:55 |
| 8 — Docs & demo script | 35 min | 18:30 |

---

## Phase 0 — Setup

Human work, not Claude Code's. Python 3.11+ installed, a virtualenv created, git
initialised, Claude Code running in the project directory. Optionally an API key in `.env`
— the app must run without one, so this is not blocking.

**Exit:** `python --version` works, virtualenv active, Claude Code responds in the repo.

## Phase 1 — Architecture

Claude Code reads `CLAUDE.md` and all of `docs/`, then produces a written proposal:

1. Stack confirmation (Option A unless told otherwise) with one line of reasoning
2. Folder structure
3. SQLAlchemy model sketch from `DATA_MODEL.md`
4. Route list (path, method, purpose)
5. Template/partial inventory per screen
6. AI service interfaces from `AI_WORKFLOWS.md`
7. Risk list — where this build is most likely to lose time

**No application code is written in this phase.** The proposal is reviewed and approved
before Phase 2. Approved decisions go into `docs/DECISIONS.md`.

**Exit:** proposal written and explicitly approved.

## Phase 2 — Skeleton

- Project structure created
- FastAPI app boots, health route responds
- SQLAlchemy models for every entity in `DATA_MODEL.md`
- Database created, seed script runs from `DEMO_DATA.md`
- Base template with nav, layout and the required disclaimer footer
- All five routes exist and render a page saying which screen it is

**Exit:** `uvicorn app.main:app --reload` starts, all five screens load without error, the
database has seed rows. Confirm by loading each URL, not by reading the code.

## Phase 3 — Core workflow

The biggest block. Build in this order — each is independently demonstrable, so if the day
runs short you still have working screens.

1. `app/services/capacity.py` with unit tests — allocation, availability, conflict
   detection. **Do this first.** Two other screens depend on it, and it is the part a
   Creative Operations reviewer will scrutinise.
2. Resource screen — table, statuses, conflict list
3. Pipeline screen — board, cards, filters, status transitions with validation
4. Project detail view
5. Dashboard — counts, deadlines, capacity summary (static text where AI will go)

**Exit:** capacity tests pass; every screen renders real seed data; a project can be moved
between columns and the change persists; an invalid transition is refused with a reason.

## Phase 4 — AI layer

1. `client.py`, `schemas.py`, `prompts.py` and `mock.py` — mocks first, so everything below
   is testable without a key
2. `analyse_brief` + the scoring rubric + the Brief Assistant screen + create-from-brief
3. `recommend_resource` + Recommendation persistence + Accept/Reject
4. `insight_to_action` + Creative Intelligence screen
5. `assess_portfolio_attention` + dashboard panel

**Exit:** every AI panel renders in mock mode; accepting a resource recommendation actually
changes assignments and the capacity numbers update; accepting a production recommendation
creates a project visible in the pipeline; with a key set, at least `analyse_brief` works
against the live provider.

If time is short here, cut in this order: (5), then (4)'s chart detail. Never cut (3) — the
accept/reject loop is the thing the whole piece argues for.

## Phase 5 — Localisation

- Localisation rows on project detail with status ladder
- Assign translator, advance status
- Deterministic risk rule, surfacing on dashboard and pipeline cards
- `check_localisation_risk` wired in

**Exit:** at least one seeded project shows a genuine localisation risk end to end.

## Phase 6 — UX polish

Layout, hierarchy, empty states, loading states on AI panels, error states, consistent
spacing, AI-generated content visually marked, disclaimer present everywhere.

This phase is the buffer. If you are behind, take from here first.

**Exit:** no screen looks unfinished; every AI panel has all three states.

## Phase 7 — Tests

- Capacity maths (already written in Phase 3)
- Brief rubric scoring
- Project creation from brief
- Recommendation accept applies the change; reject does not
- AI schema validation including a malformed response
- Localisation risk rule

Target is confidence in the demo path, not coverage.

**Exit:** `pytest` green.

## Phase 8 — Documentation and demo

Claude Code writes `README.md` (purpose, architecture, prerequisites, install, env vars,
database setup, running locally, AI configuration, demo mode, testing), completes
`docs/DEMO_SCRIPT.md`, updates `docs/DECISIONS.md`, and writes `CHANGELOG.md`.

Then: **run the demo yourself, start to finish, from a cold start.** Fresh terminal, fresh
database, no API key. If any step needs an apology, fix it or cut it.

**Exit:** a person who has never seen the repo can clone it, follow the README, and reach a
working app.

---

## Cut list, in order

If you reach 16:00 and are still in Phase 4, cut in this order and say so in the README's
"known limitations" section — a stated limitation reads as judgement, a missing feature
reads as failure:

1. Dashboard AI attention panel (replace with the deterministic list, no narration)
2. Creative Intelligence charts (a table carries the argument)
3. Pipeline filters
4. Localisation QA status (keep translation and review)
5. Phase 6 polish beyond the disclaimer and empty states

Never cut: capacity maths, the accept/reject loop, the brief readiness score, the
disclaimer.

## If a second session is available

Deployment to a public URL, a short screen-recorded walkthrough, drag-and-drop on the
pipeline, and a written portfolio piece covering problem → thinking → architecture → AI →
workflow → result.
