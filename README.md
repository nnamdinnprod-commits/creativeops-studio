# CreativeOps Studio

> Prototype concept — fictional demonstration data, based on publicly available
> information about creative operations workflows. Not affiliated with or connected
> to any company's systems.

An independent Creative Operations prototype exploring how AI, creative intelligence and
production planning could work together in a modern multi-market in-house creative studio.
It was built in roughly a day with AI-assisted development, using entirely invented data, to
demonstrate operational thinking — not as a claim of production readiness.

The single thread it argues for: **creative insight → production recommendation → capacity
check → named resource → localisation requirement → human approval → project in the
pipeline.** AI structures, flags and recommends. A human approves every state-changing
action — that's enforced in the data model, not just the UI copy.

See `docs/POSITIONING.md` for the full ethical and legal constraints this project follows,
and `docs/DECISIONS.md` for the record of every architectural decision made while building it.

## Architecture

Single Python process. No separate frontend build, no client-side framework.

- **FastAPI** serves both the pages and the form actions
- **Jinja2** templates, server-rendered; **HTMX** for the Pipeline board's in-place updates
- **SQLite + SQLAlchemy** — one file database, no server to run
- **Pydantic** validates every AI response before it reaches a template
- **pytest** for tests

```
app/
├── main.py                # FastAPI app, route registration
├── config.py               # one Settings object, reads .env
├── database.py              # SQLAlchemy engine/session
├── templates_env.py          # shared Jinja2 environment (all routes use this)
├── seed.py                    # idempotent demo data seed
├── models/                     # SQLAlchemy models — every entity in docs/DATA_MODEL.md
├── routes/                      # one file per screen, plus recommendations.py
├── services/
│   ├── capacity.py               # allocation, availability, conflict detection
│   ├── brief.py                    # readiness rubric scoring
│   ├── insight.py                   # creative-performance comparisons
│   ├── attention.py                  # dashboard "needs attention" snapshot
│   ├── localisation_risk.py           # deterministic localisation at-risk rule
│   └── ai/                             # every AI call goes through here — see below
│       ├── client.py                     # the only file importing a provider SDK
│       ├── schemas.py                     # Pydantic models for every AI input/output
│       ├── prompts.py                      # versioned prompt templates
│       ├── mock.py                          # mock implementation of every AI function
│       └── brief.py, resource.py, insight.py, risk.py, localisation.py
└── templates/                # Jinja2 templates, one per screen + shared partials
```

**The governing rule for AI:** Python computes every number shown on screen — utilisation,
readiness scores, CTR comparisons. The model only explains and recommends around
already-computed facts; it is never the source of a figure. See `docs/AI_WORKFLOWS.md`.

## Prerequisites

- Python 3.11 or newer (this project was built and tested on 3.14)
- No other services required — SQLite is a file, not a server

## Install

```bash
git clone <this-repo>
cd creativeops-scaffold
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

An API key in `.env` is **optional**. The app runs fully without one.

## Environment variables

All in `.env.example` — copy it to `.env` and adjust if needed:

| Variable | Default | Purpose |
|---|---|---|
| `AI_PROVIDER` | `mock` | `mock` \| `openai` \| `anthropic` — see AI configuration below |
| `OPENAI_API_KEY` | empty | Only read if `AI_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | empty | Only read if `AI_PROVIDER=anthropic` |
| `AI_MODEL` | empty | Model name for the selected provider; falls back to a sensible default if unset |
| `DATABASE_URL` | `sqlite:///./creativeops.db` | SQLite file location |
| `CAPACITY_TIGHT_THRESHOLD` | `85` | Allocation % above which a person is flagged "Tight" |
| `BRIEF_READINESS_THRESHOLD` | `70` | Minimum brief readiness score to leave the Ready column |

## Database setup

```bash
python -m app.seed
```

Creates the SQLite database and seeds it with fictional demo data: 8 people, 12 projects,
assignments, deliverables, localisation rows and creative-performance rows — including five
specific, verifiable situations the demo relies on (see `docs/DEMO_DATA.md`): an overloaded
designer, a viable reassignment target, a genuinely vague brief, a French localisation gap,
and a German creative-performance pattern worth acting on.

Idempotent — running it again does nothing if data already exists. To start over from a
clean state:

```bash
python -m app.seed --reset
```

## Running locally

```bash
uvicorn app.main:app --reload
```

Then open **http://localhost:8000** — it redirects to the Dashboard. Five screens: Dashboard,
Pipeline, Resources, Brief Assistant, Creative Intelligence.

## AI configuration

`AI_PROVIDER=mock` (the default) uses curated mock responses that read the same computed
facts a live model would — so the demo stays coherent with whatever's on screen, and runs
with zero network dependency. This is the recommended way to run the demo: no key required,
no latency, no risk of a live call failing mid-presentation.

To use a live provider instead, set `AI_PROVIDER=openai` or `AI_PROVIDER=anthropic` and the
matching API key in `.env`. Every screen's footer shows which mode is active ("Mode: mock" /
"Mode: openai" / "Mode: anthropic") so it's never ambiguous which one is running.

Whichever mode is active, every AI response is validated against a Pydantic schema before it
reaches a template. A malformed or failed response renders a plain fallback message and a
retry control — never a traceback, never raw model output.

## Testing

```bash
pytest
```

33 tests covering: capacity math (allocation, overlap detection, conflict thresholds), the
brief readiness rubric, AI schema validation including the "invention guard" (an AI response
referencing a project not in its input is dropped, not rendered), the localisation risk rule,
project creation from a brief end-to-end, and the recommendation accept/reject cycle
(accepting actually changes state; rejecting doesn't, and stays in history).

No test makes a live API call — everything runs against the mock layer or fixture responses.

## Demo mode

For presenting this: reset to a clean seed before each run (`python -m app.seed --reset`),
and leave `AI_PROVIDER=mock` unless you specifically intend to show a live call. See
`docs/DEMO_SCRIPT.md` for the full walkthrough with real project names and numbers from the
seed data.

## Known limitations

This is a one-day V1 build. Deliberately out of scope, per `docs/BUILD_PLAN.md` and
`docs/PRODUCT_SPEC.md`:

- No authentication — anyone with the URL can act as "Demo User"
- No real third-party integrations — everything under `app/services/ai/` that isn't
  `mock.py` talks to OpenAI or Anthropic directly if configured; nothing else is wired up
- No deployment infrastructure, no containers, no background jobs
- No drag-and-drop on the Pipeline board — status changes are a dropdown + button, by design
  (an invalid move needs to show *why* it's refused, which a drag gesture can't do as clearly)
- `Project.risk_level` / `risk_reason` columns exist in the schema but are always their
  default — risk badges are computed live from current data instead of a stored, synced
  value (see decision 012 in `docs/DECISIONS.md`)
- Mobile is not a target — built and tested at laptop width

## What's next, if this continues

Real integration behind the existing mock boundary in `app/services/ai/`, historical capacity
data to make effort estimates learned rather than assumed, and authentication.
