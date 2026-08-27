from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import Assumption, RateBand
from app.services.assumptions import reset_all

router = APIRouter()

CATEGORY_ORDER = ["Review and approval cycles", "Lead times", "Volume scaling", "Confidence bands"]


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
    return RedirectResponse(url="/assumptions", status_code=303)


@router.post("/assumptions/reset")
def reset_assumptions(db: Session = Depends(get_db)):
    reset_all(db)
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
