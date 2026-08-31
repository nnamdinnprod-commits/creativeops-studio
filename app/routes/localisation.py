from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import Localisation, LocalisationStatus, Person, PersonRole, Project
from app.services.localisation_risk import summarize_by_market

router = APIRouter()

STAGE_ORDER = [
    LocalisationStatus.not_started,
    LocalisationStatus.in_translation,
    LocalisationStatus.in_review,
    LocalisationStatus.qa,
    LocalisationStatus.approved,
]

STAGE_LABELS = {
    LocalisationStatus.not_started: "Not started",
    LocalisationStatus.in_translation: "In translation",
    LocalisationStatus.in_review: "In review",
    LocalisationStatus.qa: "QA",
    LocalisationStatus.approved: "Approved",
}


@router.get("/localisation")
def localisation_screen(request: Request, market: str | None = None, stage: str | None = None,
                        assign_error: str | None = None, db: Session = Depends(get_db)):
    all_rows = db.query(Localisation).all()
    projects_by_id = {p.id: p for p in db.query(Project).all()}

    rows = all_rows
    if market:
        rows = [r for r in rows if r.target_market == market]
    if stage:
        rows = [r for r in rows if r.status.value == stage]

    project_ids = sorted({r.project_id for r in rows if r.project_id in projects_by_id})
    all_markets = sorted({r.target_market for r in all_rows})

    # grid[project_id][market] = Localisation row, for the cells the filters leave in scope
    grid: dict[int, dict[str, Localisation]] = {}
    for r in rows:
        if r.project_id not in projects_by_id:
            continue
        grid.setdefault(r.project_id, {})[r.target_market] = r

    market_summaries = summarize_by_market(db)
    people_by_id = {p.id: p for p in db.query(Person).all()}
    translators = db.query(Person).filter_by(role=PersonRole.translator).all()

    return templates.TemplateResponse(request, "localisation.html", {
        "grid": grid,
        "project_ids": project_ids,
        "projects_by_id": projects_by_id,
        "all_markets": all_markets,
        "market_summaries": market_summaries,
        "people_by_id": people_by_id,
        "translators": translators,
        "stage_order": STAGE_ORDER,
        "stage_labels": STAGE_LABELS,
        "selected_market": market,
        "selected_stage": stage,
        "assign_error": assign_error,
        # Never carries assign_error forward — a stale refusal from a previous
        # attempt shouldn't be re-attached to the next one's redirect target.
        "return_to": "/localisation" + (f"?market={market}" if market else "")
                    + (("&" if market else "?") + f"stage={stage}" if stage else ""),
    })
