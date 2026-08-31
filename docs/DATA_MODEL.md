# Data Model — V1

SQLite via SQLAlchemy. Keep it simple; resist adding tables that no screen reads.

Convention: every table has `id` (int PK), `created_at`, `updated_at`.

## Project

The central entity.

| Field | Type | Notes |
|---|---|---|
| `name` | str | |
| `brand` | str | FK-free string in V1; see Brand note below |
| `campaign` | str | |
| `source_market` | str | ISO-ish code: NL, DE, FR, UK, ES |
| `priority` | enum | `low` / `medium` / `high` / `critical` |
| `status` | enum | `brief` / `ready` / `assigned` / `in_production` / `creative_review` / `waiting_on_client` / `approved` / `delivered` / `on_hold` / `cancelled` / `archived`. `waiting_on_client` splits out of what Creative Review used to conflate — "we are reviewing" vs "they are sitting on it" (REVIEW_02.md P5.4). `on_hold`/`cancelled`/`archived` are exception states, not pipeline stages — always exempt from the readiness gate and excluded from the dashboard's active-project counts. |
| `deadline` | date | |
| `owner_id` | FK → Person | the producer accountable, not the person doing the work |
| `brief_raw` | text | the original messy request |
| `brief_analysis_id` | FK → BriefAnalysis, nullable | |
| `risk_level` | enum | `none` / `low` / `medium` / `high` — computed, not manually set |
| `risk_reason` | text, nullable | computed |
| `localisation_required` | bool | |
| `estimated_days` | float, nullable | |
| `production_tempo` | enum | `fast_track` / `standard` / `full_production`, default `standard`. Scopes the readiness gate (below) — pipeline stage sequence itself is unrestricted regardless of tempo. REVIEW_02.md P5.3. |
| `status_reason` | text, nullable | the most recent reason given for a hold, cancel, or backward move — not a full history. REVIEW_02.md P5.4. |

**Brand** stays a string in V1. A brands table earns its place only when a screen needs
brand-level attributes. Note the decision in `DECISIONS.md` if that changes.

## Person

| Field | Type | Notes |
|---|---|---|
| `name` | str | invented first names only — see POSITIONING.md |
| `role` | enum | `producer` / `designer` / `senior_designer` / `motion_designer` / `copywriter` / `translator` |
| `capacity_pct` | int | contracted availability, e.g. 80 for 4 days/week |
| `skills` | str | comma-separated in V1; JSON only if a query needs it |
| `is_external` | bool | distinguishes internal team from external partner/vendor |

`allocated_pct` is **not** a column. It is computed from Assignment rows for a given date
window by `app/services/capacity.py`. Storing it would let it drift.

## Assignment

Links a person to a project for a period at a percentage.

| Field | Type | Notes |
|---|---|---|
| `project_id` | FK → Project | |
| `person_id` | FK → Person | |
| `allocation_pct` | int | share of that person's working time |
| `start_date` | date | |
| `end_date` | date | |
| `role_on_project` | str, nullable | |
| `project_phase_id` | FK → ProjectPhase, nullable | Session 2 addition — set only when `app/services/assignment.py`'s `assign_phase()` created this row, so a reassignment can find and replace exactly that row (`DECISIONS.md` 021) |

Overlap across assignments is what creates capacity conflicts. The seed data must produce
at least two genuine overlaps.

## Deliverable

| Field | Type | Notes |
|---|---|---|
| `project_id` | FK → Project | |
| `type` | enum | `social_static` / `social_video` / `paid_display` / `homepage_banner` / `email` / `motion` |
| `market` | str | |
| `format_spec` | str, nullable | e.g. "1080x1080", "16:9 15s" |
| `status` | enum | `not_started` / `in_progress` / `in_review` / `approved` / `delivered` |
| `deadline` | date, nullable | |

## Localisation

One row per target market per project.

| Field | Type | Notes |
|---|---|---|
| `project_id` | FK → Project | |
| `target_market` | str | |
| `language` | str | |
| `translator_id` | FK → Person, nullable | null is a risk signal |
| `status` | enum | `not_started` / `in_translation` / `in_review` / `qa` / `approved` |
| `review_status` | enum | `pending` / `in_progress` / `passed` / `failed` |
| `qa_status` | enum | `pending` / `in_progress` / `passed` / `failed` |
| `due_date` | date, nullable | |

## CreativeInsight

Mock performance data and its derived insight. See POSITIONING.md — this is synthetic.

| Field | Type | Notes |
|---|---|---|
| `brand` | str | |
| `market` | str | |
| `format` | str | |
| `variant_theme` | enum | `lifestyle` / `product_only` / `ugc` / `promotional` |
| `impressions` | int | |
| `ctr` | float | |
| `engagement_rate` | float | |
| `conversion_rate` | float | |
| `period_start` / `period_end` | date | |
| `insight_text` | text, nullable | AI-generated summary of a grouping |
| `dismissed_reason` | text, nullable | set (identically across a market's lifestyle/product_only rows) when a producer decides not to act on this market's opportunity. The rest of an insight's lifecycle (`new` / `recommendation_pending` / `actioned`) is never stored — derived at display time from whether a pending or accepted `production_action` Recommendation exists for that market (`app/services/insight.py::compute_insight_status`). REVIEW_02.md P4. |

## Recommendation

**The table that makes "humans stay in control" real rather than decorative.** Every AI
suggestion that would change state is persisted here first.

| Field | Type | Notes |
|---|---|---|
| `kind` | enum | `resource_reallocation` / `production_action` / `risk_intervention` / `localisation_action` |
| `project_id` | FK → Project, nullable | |
| `payload_json` | text | the structured, validated AI output |
| `rationale` | text | human-readable explanation shown in the UI |
| `computed_facts_json` | text | the deterministic numbers passed *into* the model — kept for auditability |
| `status` | enum | `pending` / `accepted` / `rejected` |
| `decided_by` | str, nullable | demo user name |
| `decided_at` | datetime, nullable | |
| `outcome_note` | text, nullable | what changed when accepted |

Accepting a recommendation applies its effect in a single transaction and records the
outcome. Rejecting keeps it in history. Nothing else in the system may mutate assignments
or project status from AI output directly.

## BriefAnalysis

The structured result of parsing a messy brief.

| Field | Type | Notes |
|---|---|---|
| `raw_text` | text | |
| `extracted_json` | text | validated `BriefExtraction` payload |
| `readiness_score` | int | 0–100, computed in Python from the rubric |
| `missing_fields_json` | text | list of field keys |
| `blocking_reasons` | text | why each gap matters |
| `created_project_id` | FK → Project, nullable | |

The readiness score is computed by `app/services/brief.py` from the extraction, using a
fixed weighted rubric. The model extracts fields; Python scores them. This keeps the score
stable across runs and unit-testable.

## ProjectType / PhaseTemplate

Session 2 addition — see `docs/PLANNING.md` for the full spec (phase templates per type,
back-scheduling algorithm, timeline view). Seeded by `app/seed.py`'s `seed_phase_templates()`,
four types (Film / branded content, Event, Stills, Social / AI-generated content), 43 phase
rows total across two owner review rounds.

| Field | Type | Notes |
|---|---|---|
| `ProjectType.name` | str | |
| `ProjectType.description` | text, nullable | |
| `PhaseTemplate.project_type_id` | FK → ProjectType | |
| `PhaseTemplate.sequence` | int | 1-indexed, contiguous per type |
| `PhaseTemplate.name` | str | |
| `PhaseTemplate.default_days` | int | 0 for a pure zero-duration milestone marker |
| `PhaseTemplate.kind` | enum | `prep` / `production` / `review` / `delivery` |
| `PhaseTemplate.required_roles` | str | comma-separated `PersonRole` values, same convention as `Person.skills` |
| `PhaseTemplate.is_milestone` | bool | |
| `PhaseTemplate.is_client_review` | bool | |
| `PhaseTemplate.scales_with_volume` | bool | |

`Project` gained two columns for this: `project_type_id` (FK → ProjectType, nullable — every
project seeded or created before this column existed has neither a type nor a schedule) and
`volume_factor` (float, default 1.0). Not yet wired into the Brief Assistant's create-project
flow — a project gets a type only if set directly, e.g. by a test or a future screen.

## ProjectPhase

A generated, dated instance of a `PhaseTemplate` row for one project. Produced by
`app/services/scheduling.py`'s `generate_schedule()`, never hand-written. Regenerating a
project's schedule replaces its existing `ProjectPhase` rows rather than appending.

| Field | Type | Notes |
|---|---|---|
| `project_id` | FK → Project | |
| `name` | str | copied from the source `PhaseTemplate` row |
| `kind` | enum | `prep` / `production` / `review` / `delivery` |
| `start_date` / `end_date` | date | computed by `back_schedule()` |
| `is_milestone` | bool | copied from the source template row |
| `is_anchored` | bool | always `False` today — anchored-phase support isn't built yet (see `DECISIONS.md` 018) |
| `status` | enum | `not_started` / `in_progress` / `complete` — `PLANNING.md` doesn't specify values for this field; inferred to match the shape used by `Deliverable`/`Localisation` elsewhere, logged in `DECISIONS.md` 019 |
| `assigned_person_id` | FK → Person, nullable | set by `app/services/assignment.py`'s `assign_phase()`, at `/timeline` (`DECISIONS.md` 021) |
| `required_roles` | str | not in `PLANNING.md`'s column list — comma-separated `PersonRole` values, copied from the source `PhaseTemplate` row at generation time so a phase is self-sufficient for candidate matching even without its template (`DECISIONS.md` 021) |

Rendered at `/timeline` (`DECISIONS.md` 020); production, non-milestone phases are assignable
there (`DECISIONS.md` 021). Nothing writes `status` yet.

## Relationship summary

```
Person ──< Assignment >── Project ──< Deliverable
   │                         │
   └──< Localisation >───────┤
                             ├──< Recommendation
                             └─── BriefAnalysis

CreativeInsight ── (brand, market) ─→ informs Recommendation
```

CreativeInsight links to projects loosely by brand and market rather than by FK, because
an insight is about a market's creative performance, not about one project.

## Assumption / RateBand

Session 3 addition — see `docs/ASSUMPTIONS.md` for the full spec and `docs/DECISIONS.md` 025
for what's built vs. not yet wired. Seeded by `app/seed.py`'s `seed_assumptions()`: 21
`Assumption` rows across four categories (Review and approval cycles, Lead times, Volume
scaling, Confidence bands), 6 `RateBand` rows (one per `PersonRole`). Rendered and editable
at `/assumptions`.

| Field | Type | Notes |
|---|---|---|
| `Assumption.category` | str | one of the four category names above |
| `Assumption.key` | str | unique, e.g. `client_review_days` |
| `Assumption.value_numeric` | float, nullable | the live value |
| `Assumption.value_text` | str, nullable | unused today — every seeded assumption is numeric |
| `Assumption.unit` | str, nullable | e.g. `days`, `factor`, `rounds` |
| `Assumption.default_value` | float, nullable | what "reset to defaults" restores |
| `Assumption.description` | text | shown in the UI as a short note on what it affects |
| `Assumption.affects` | str, nullable | e.g. `scheduling, costing` |
| `RateBand.role` | enum (`PersonRole`) | one row per role |
| `RateBand.low` / `RateBand.high` | float | day-rate range |
| `RateBand.currency` | str | always `EUR` today — multi-currency is out of scope per `BRIEF_MODES.md` |
| `RateBand.lead_time_days` | int | REVIEW_02.md P5.5: days notice before an external engagement of this role can start. Read by `app/services/assignment.py`'s `earliest_feasible_start()`/`engage_person()`; internal Team members never read it. |

Not yet read by `app/services/scheduling.py` (which still uses its own hardcoded
`CLIENT_REVIEW_DAYS`/`VOLUME_SCALE_BANDS` constants) or by anything else — Quick Estimate
mode (Session C step 2) is the first real consumer.
