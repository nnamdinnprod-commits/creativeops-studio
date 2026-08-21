import json
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import CreativeInsight, Person, PersonRole, Project, Recommendation, RecommendationKind
from app.services.ai.insight import insight_to_action
from app.services.capacity import all_person_capacities
from app.services.insight import compute_market_comparisons

router = APIRouter()

BRANDS = ["Albelli", "Photobox", "Hofmann"]


def _screen_context(db: Session):
    insights = db.query(CreativeInsight).order_by(CreativeInsight.market, CreativeInsight.variant_theme).all()
    comparisons = compute_market_comparisons(insights)

    recommendations = (
        db.query(Recommendation)
        .filter_by(kind=RecommendationKind.production_action)
        .order_by(Recommendation.created_at.desc())
        .all()
    )
    recommendations_view = [
        {"rec": rec, "payload": json.loads(rec.payload_json)} for rec in recommendations
    ]
    people_by_id = {p.id: p for p in db.query(Person).all()}
    projects_by_id = {p.id: p for p in db.query(Project).all()}

    return {
        "insights": insights,
        "comparisons": comparisons,
        "brands": BRANDS,
        "recommendations": recommendations_view,
        "people_by_id": people_by_id,
        "projects_by_id": projects_by_id,
    }


@router.get("/intelligence")
def intelligence(request: Request, error: str | None = None, db: Session = Depends(get_db)):
    context = _screen_context(db)
    context["recommend_failed"] = error == "recommend_failed"
    context["no_candidates"] = error == "no_candidates"
    return templates.TemplateResponse(request, "intelligence.html", context)


@router.post("/intelligence/recommend")
def recommend(request: Request, market: str = Form(...), brand: str = Form(...),
             db: Session = Depends(get_db)):
    insights = db.query(CreativeInsight).all()
    comparisons = compute_market_comparisons(insights)
    match = next((c for c in comparisons if c["market"] == market), None)
    if match is None:
        return RedirectResponse(url="/intelligence?error=recommend_failed", status_code=303)

    # The deliverable is visual production work — only design-capable roles are
    # feasible candidates. A producer or translator having spare capacity doesn't
    # make them able to do the work.
    _DESIGN_ROLES = {PersonRole.designer, PersonRole.senior_designer, PersonRole.motion_designer}
    capacities = all_person_capacities(db, on_date=date.today())
    capacity_snapshot = [
        {
            "id": c.person.id,
            "name": c.person.name,
            "available_pct": c.available_pct,
            "skills": [s.strip() for s in c.person.skills.split(",") if s.strip()],
        }
        for c in capacities
        if c.available_pct > 0 and not c.person.is_external and c.person.role in _DESIGN_ROLES
    ]
    if not capacity_snapshot:
        return RedirectResponse(url="/intelligence?error=no_candidates", status_code=303)

    rec = insight_to_action(match, capacity_snapshot)
    if rec is None:
        return RedirectResponse(url="/intelligence?error=recommend_failed", status_code=303)

    facts = dict(match)
    facts["brand"] = brand
    db.add(Recommendation(
        kind=RecommendationKind.production_action,
        project_id=None,
        payload_json=rec.model_dump_json(),
        rationale=rec.recommended_action,
        computed_facts_json=json.dumps(facts, default=str),
    ))
    db.commit()

    return RedirectResponse(url="/intelligence", status_code=303)
