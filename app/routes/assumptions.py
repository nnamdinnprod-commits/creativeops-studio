from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import Assumption, Project, ProjectPhase, RateBand
from app.services.assumptions import reset_all
from app.services.estimate import PRODUCTION_SCALE_LABELS, PRODUCTION_SCALE_TIER_ORDER, TERRITORY_LABELS
from app.services.scheduling import generate_schedule

router = APIRouter()

CATEGORY_ORDER = ["Review and approval cycles", "Lead times", "Volume scaling",
                  "Territory factor", "Confidence bands"]

# REVIEW_03.md R9.1: "the same failure as 'rows,' one layer deeper" — the raw
# key was the only label this page ever gave a value, and a database column
# name is not something a Creative Ops reviewer should have to read. Hand-
# written rather than a mechanical key.replace('_', ' ') — "Client review
# round" reads better than "Client review days" ever would, and there are
# only 13 of these (confidence bands are handled separately below).
ASSUMPTION_LABELS = {
    "client_review_days": "Client review round",
    "client_review_minimum_days": "Minimum client review (compressed)",
    "internal_review_days": "Internal review round",
    "default_review_rounds": "Assumed review rounds",
    "localisation_review_days": "Localisation review, per market",
    "fabrication_lead_days": "Fabrication lead time",
    "talent_booking_lead_days": "Talent booking lead time",
    "location_permit_lead_days": "Location permit lead time",
    "translation_turnaround_days": "Translation turnaround",
    "volume_scale_1_6": "Volume scaling, 1–6 assets",
    "volume_scale_7_15": "Volume scaling, 7–15 assets",
    "volume_scale_16_30": "Volume scaling, 16–30 assets",
    "volume_scale_31_60": "Volume scaling, 31–60 assets",
}
# Derived from estimate.py's own TERRITORY_LABELS rather than restated here —
# one name per territory, not two copies that could drift apart.
ASSUMPTION_LABELS.update({
    f"territory_factor_{territory}": label for territory, label in TERRITORY_LABELS.items()
})

# REVIEW_03.md R9.3: "volume scaling needs its reason" — a fixed sentence
# above the category's table rather than repeated per row, since the reason
# is the same for all four bands. The 2.5x/3.3x example is the actual
# volume_scale_16_30 factor against a naive linear read of the same range —
# not an invented illustration.
VOLUME_SCALING_NOTE = (
    "Effort grows more slowly than asset count, because setup is a fixed cost — "
    "twenty assets take roughly 2.5× the time of six, not 3.3×."
)

# REVIEW_03.md R9.2: "eight rows becomes four, expressed as what the user
# sees" — a range a producer reads directly, not two separate multipliers
# they'd have to do the arithmetic on themselves.
CONFIDENCE_TIER_LABELS = {
    "high": "Fully specified",
    "medium": "Mostly specified",
    "low_medium": "Partly assumed",
    "low": "Mostly assumed",
}
CONFIDENCE_TIER_ORDER = ["high", "medium", "low_medium", "low"]


def _signed_pct(factor: float) -> str:
    pct = round((factor - 1) * 100)
    return f"{'+' if pct >= 0 else ''}{pct}%"


def _currency_range(low: float, high: float) -> str:
    return f"€{low:,.0f}–€{high:,.0f}"

# REVIEW_02.md P3: "Change an assumption -> reschedule every affected project."
# Every other assumption (volume scaling, lead times, confidence bands,
# client_review_minimum_days) is already read live at display time by
# compute_estimate()/build_feasibility_facts() — there's nothing stored to go
# stale. client_review_days is the one exception: generate_schedule() reads it
# once and persists the result as ProjectPhase rows, so an edit here only takes
# effect once those rows are regenerated.
_KEYS_REQUIRING_RESCHEDULE = {"client_review_days"}


def _reschedule_every_scheduled_project(db: Session) -> None:
    scheduled_project_ids = [row[0] for row in db.query(ProjectPhase.project_id).distinct().all()]
    for project_id in scheduled_project_ids:
        project = db.get(Project, project_id)
        if project is not None and project.project_type_id is not None:
            generate_schedule(db, project)


@router.get("/assumptions")
def assumptions(request: Request, db: Session = Depends(get_db)):
    all_assumptions = db.query(Assumption).all()
    by_category: dict[str, list[Assumption]] = {c: [] for c in CATEGORY_ORDER}
    for a in all_assumptions:
        by_category.setdefault(a.category, []).append(a)
    for rows in by_category.values():
        rows.sort(key=lambda a: a.key)

    # REVIEW_03.md R9.2: confidence bands render as their own section below,
    # not through the generic per-key table — pulled out of by_category so
    # the generic loop's category list doesn't also render them.
    confidence_by_key = {a.key: a for a in by_category.pop("Confidence bands", [])}
    confidence_rows = []
    for tier in CONFIDENCE_TIER_ORDER:
        low = confidence_by_key.get(f"confidence_{tier}_low_factor")
        high = confidence_by_key.get(f"confidence_{tier}_high_factor")
        if low is None or high is None:
            continue
        confidence_rows.append({
            "label": CONFIDENCE_TIER_LABELS[tier],
            "low": low,
            "high": high,
            "range_display": f"{_signed_pct(low.value_numeric)} / {_signed_pct(high.value_numeric)}",
        })

    # REVIEW_03.md R4: same collapse as confidence bands above — eight low/high
    # tier rows plus the marginal-cost pair become five rows a producer reads
    # as ranges, not ten numbers they'd have to pair up themselves.
    scale_by_key = {a.key: a for a in by_category.pop("Production scale", [])}
    production_scale_rows = []
    for tier in PRODUCTION_SCALE_TIER_ORDER:
        low = scale_by_key.get(f"production_scale_{tier}_low")
        high = scale_by_key.get(f"production_scale_{tier}_high")
        if low is None or high is None:
            continue
        production_scale_rows.append({
            "label": PRODUCTION_SCALE_LABELS[tier],
            "low": low,
            "high": high,
            "range_display": _currency_range(low.value_numeric, high.value_numeric),
        })
    marginal_low = scale_by_key.get("multi_brand_marginal_cost_low")
    marginal_high = scale_by_key.get("multi_brand_marginal_cost_high")
    if marginal_low is not None and marginal_high is not None:
        production_scale_rows.append({
            "label": "Each additional brand (marginal)",
            "low": marginal_low,
            "high": marginal_high,
            "range_display": _currency_range(marginal_low.value_numeric, marginal_high.value_numeric),
        })

    # REVIEW_03.md R4 follow-up: the coverage note is a sentence, not a
    # number/range, so it's pulled out of scale_by_key on its own rather than
    # folded into production_scale_rows's low/high shape.
    coverage_note = scale_by_key.get("production_cost_coverage_note")

    rate_bands = db.query(RateBand).order_by(RateBand.role).all()

    return templates.TemplateResponse(request, "assumptions.html", {
        "category_order": [c for c in CATEGORY_ORDER if by_category.get(c)],
        "by_category": by_category,
        "assumption_labels": ASSUMPTION_LABELS,
        "volume_scaling_note": VOLUME_SCALING_NOTE,
        "confidence_rows": confidence_rows,
        "production_scale_rows": production_scale_rows,
        "coverage_note": coverage_note,
        "rate_bands": rate_bands,
    })


@router.post("/assumptions/{assumption_id}/update")
def update_assumption(assumption_id: int, value_numeric: float = Form(...),
                      db: Session = Depends(get_db)):
    assumption = db.get(Assumption, assumption_id)
    if assumption is not None:
        assumption.value_numeric = value_numeric
        db.commit()
        if assumption.key in _KEYS_REQUIRING_RESCHEDULE:
            _reschedule_every_scheduled_project(db)
    return RedirectResponse(url="/assumptions", status_code=303)


@router.post("/assumptions/{assumption_id}/update-text")
def update_text_assumption(assumption_id: int, value_text: str = Form(...),
                           db: Session = Depends(get_db)):
    assumption = db.get(Assumption, assumption_id)
    if assumption is not None:
        assumption.value_text = value_text
        db.commit()
    return RedirectResponse(url="/assumptions", status_code=303)


@router.post("/assumptions/reset")
def reset_assumptions(db: Session = Depends(get_db)):
    reset_all(db)
    _reschedule_every_scheduled_project(db)
    return RedirectResponse(url="/assumptions", status_code=303)


@router.post("/assumptions/rate-bands/{rate_band_id}/update")
def update_rate_band(rate_band_id: int, low: float = Form(...), high: float = Form(...),
                     lead_time_days: int = Form(...), db: Session = Depends(get_db)):
    rate_band = db.get(RateBand, rate_band_id)
    if rate_band is not None:
        rate_band.low = low
        rate_band.high = high
        rate_band.lead_time_days = lead_time_days
        db.commit()
    return RedirectResponse(url="/assumptions", status_code=303)
