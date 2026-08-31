from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import Assumption, Project, ProjectPhase, RateBand
from app.services.assumptions import reset_all
from app.services.scheduling import generate_schedule

router = APIRouter()

CATEGORY_ORDER = ["Review and approval cycles", "Lead times", "Volume scaling", "Confidence bands"]

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

    rate_bands = db.query(RateBand).order_by(RateBand.role).all()

    return templates.TemplateResponse(request, "assumptions.html", {
        "category_order": [c for c in CATEGORY_ORDER if by_category.get(c)],
        "by_category": by_category,
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


@router.post("/assumptions/reset")
def reset_assumptions(db: Session = Depends(get_db)):
    reset_all(db)
    _reschedule_every_scheduled_project(db)
    return RedirectResponse(url="/assumptions", status_code=303)


@router.post("/assumptions/rate-bands/{rate_band_id}/update")
def update_rate_band(rate_band_id: int, low: float = Form(...), high: float = Form(...),
                     db: Session = Depends(get_db)):
    rate_band = db.get(RateBand, rate_band_id)
    if rate_band is not None:
        rate_band.low = low
        rate_band.high = high
        db.commit()
    return RedirectResponse(url="/assumptions", status_code=303)
