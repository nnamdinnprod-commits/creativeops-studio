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
