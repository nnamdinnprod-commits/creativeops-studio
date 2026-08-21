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
| `status` | enum | `brief` / `ready` / `assigned` / `in_production` / `creative_review` / `approved` / `delivered` |
| `deadline` | date | |
| `owner_id` | FK → Person | the producer accountable, not the person doing the work |
| `brief_raw` | text | the original messy request |
| `brief_analysis_id` | FK → BriefAnalysis, nullable | |
| `risk_level` | enum | `none` / `low` / `medium` / `high` — computed, not manually set |
| `risk_reason` | text, nullable | computed |
| `localisation_required` | bool | |
| `estimated_days` | float, nullable | |

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
