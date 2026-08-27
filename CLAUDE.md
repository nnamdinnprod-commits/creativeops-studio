# CreativeOps Studio — Project Rules

Standing instructions for every session in this repo. Read this fully; it is short by design.

## What this is

A portfolio prototype demonstrating how AI, creative intelligence and production planning
connect in a multi-market in-house creative studio. It is built to be understood by a
Creative Operations leader in a five-minute demo, not to be sold as enterprise software.

The owner is a Creative Operations professional, not a career software engineer. Explain
decisions in plain language. When something breaks, say what broke and what you are doing
about it — do not silently work around it.

## Read before you edit

`docs/` is the source of truth for product decisions. Before changing code in an area,
read the doc that governs it:

| Doc | Governs |
|---|---|
| `docs/PRODUCT_SPEC.md` | Screens, features, what each view must show |
| `docs/DATA_MODEL.md` | Entities, fields, relationships |
| `docs/AI_WORKFLOWS.md` | Every AI function, its JSON contract, its mock |
| `docs/POSITIONING.md` | Legal/ethical constraints on naming and data — **non-negotiable** |
| `docs/BUILD_PLAN.md` | Phase order, time boxes, per-phase exit criteria |
| `docs/DEMO_DATA.md` | Seed data and the conflicts it must produce |
| `docs/DECISIONS.md` | Log of architectural decisions and why |
| `docs/FEEDBACK_LOG.md` | Owner review notes and the prioritised change list (Sessions A/B/C) |
| `docs/PLANNING.md` | Session 2 spec: phase templates, back-scheduling, timeline view — not yet built |
| `docs/BRIEF_MODES.md` | Session 2 spec: Quick Estimate / Full Brief modes — not yet built |
| `docs/ASSUMPTIONS.md` | Session 2 spec: editable planning assumptions and rate bands — not yet built |

If code and docs disagree, stop and ask which is wrong. Do not quietly change the docs to
match the code.

## Non-negotiables

These are the constraints most likely to cause real-world harm if broken. They override
convenience, speed and anything else in this file.

1. **Fictional data is always labelled fictional.** Every screen carries a visible
   disclaimer. Never generate content implying this system holds real company data.
2. **The app is never named after a real company.** It is "CreativeOps Studio". Real brand
   names appear only as fictional demo tenants, clearly marked.
3. **No fake integrations presented as real.** Anything simulating a third-party service
   lives in a module named `mock_*`, and the UI says "mock data" wherever it surfaces.
4. **No real credentials, ever.** Secrets come from environment variables. `.env` is
   gitignored. Never write an API key into a file that gets committed.
5. **AI recommends; humans decide.** Every AI recommendation is persisted with an explicit
   `pending / accepted / rejected` state and requires a click to act on. No AI output
   mutates project or assignment state without a recorded human approval.

## Stack

Single-process only. A separate frontend dev server talking to a separate backend is
banned for V1 — that split is where a one-day build dies (CORS, two terminals, npm drift).

**Default: Option A.** Python 3.11+, FastAPI, Jinja2 templates, HTMX for interactivity,
Alpine.js for local UI state, Tailwind via CDN, SQLite + SQLAlchemy, Pydantic for
validation, pytest for tests. One `uvicorn` command runs everything. No build step.

**Option B, only if the owner explicitly asks for a publicly deployable URL as part of V1
and says they are comfortable with Node tooling:** Next.js App Router, server actions,
SQLite via better-sqlite3 (or Postgres if deploying).

Do not propose any other stack. Do not add a client-side framework to Option A.

## Scope

**Build in V1:** dashboard, kanban pipeline, resource/capacity planning, AI brief
assistant, creative-intelligence-to-production recommendation, basic localisation
tracking, seeded demo data, tests on the critical paths, documentation.

**Do not build in V1:** authentication, real third-party integrations, deployment
infrastructure, microservices, containers, agent orchestration frameworks, websockets or
real-time collaboration, a digital asset manager, a translation management system,
drag-and-drop, file uploads, email or notifications.

If a task threatens the one-day budget, simplify it and say so. Adding scope without
asking is the most expensive mistake available here.

## Working method

- Follow `docs/BUILD_PLAN.md` phase by phase. Do not start a phase before the previous
  phase's exit criteria pass.
- **Run the app after every phase.** A phase is not done because the code looks right; it
  is done when the server starts and the screen renders.
- Keep changes small enough to review. Prefer several focused edits over one large rewrite.
- When you finish a phase, state what works, what is stubbed, and what is next.
- Do not generate large volumes of speculative code. Build the thing that is needed now.

## Code rules

Rules below are checkable — a reviewer can tell at a glance whether they were followed.

- Type hints on every function signature under `app/`.
- All AI calls go through `app/services/ai/`. No provider SDK is imported anywhere else.
- Every AI response is parsed into a Pydantic model before it reaches a template. A
  malformed response renders a fallback message, never a traceback and never raw text.
- Every AI function has a mock returning the identical shape. The app runs fully with no
  API key set.
- **Capacity and allocation maths are deterministic Python, not AI.** The AI explains and
  recommends; `app/services/capacity.py` computes. Anything shown as a number has a unit
  test.
- Database access goes through the FastAPI session dependency. No module-level connections.
- Configuration reads from environment via one settings object. No literal config values
  scattered in application code.
- New dependency means: added to `requirements.txt`, and one line in `docs/DECISIONS.md`
  saying why.
- Comments explain *why*, not *what*. Do not narrate the obvious.

## Working with the owner

Before each significant step, say in two or three plain sentences what you are about to do
and why, in language a non-engineer can follow. After each step, say what changed and what
I can look at in the browser to verify it. Explain intent and consequence, not syntax. If I
approve something that contradicts the docs, tell me before doing it.

## When you are stuck

If the same error survives two fix attempts, stop. Report what you tried, what the error
says, and what you think is happening. Do not try a third variation of the same approach,
and do not disable the failing check to make it pass.
