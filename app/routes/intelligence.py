import json
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import (
    CreativeInsight,
    Person,
    PersonRole,
    Project,
    Recommendation,
    RecommendationKind,
    RecommendationStatus,
)
from app.services.ai.insight import insight_to_action
from app.services.capacity import all_person_capacities
from app.services.insight import (
    compute_insight_status,
    compute_market_comparisons,
    dismiss_market_insight,
    distinct_periods,
)

router = APIRouter()

BRANDS = ["Fotomera", "Halveth", "Cassenvale"]


def _screen_context(db: Session, period_end: date | None = None):
    # REVIEW_02.md P6.2: "labelled with an explicit reporting period... with a
    # period selector" — every distinct period actually in the data, most recent
    # selected by default. Both the metrics table and the comparisons are scoped
    # to whichever one is selected; creative performance reporting is periodic in
    # reality, and pretending otherwise is what made the table read as broken
    # rather than as a snapshot.
    periods = distinct_periods(db)
    selected_period = next((p for p in periods if p[1] == period_end), periods[0]) if periods else None

    insights = (
        db.query(CreativeInsight)
        .filter(CreativeInsight.period_start == selected_period[0],
               CreativeInsight.period_end == selected_period[1])
        .order_by(CreativeInsight.market, CreativeInsight.variant_theme)
        .all()
        if selected_period else []
    )
    comparisons = compute_market_comparisons(insights)
    insight_status_by_market = {c["market"]: compute_insight_status(db, c["market"]) for c in comparisons}

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
        "insight_status_by_market": insight_status_by_market,
        "brands": BRANDS,
        "recommendations": recommendations_view,
        "people_by_id": people_by_id,
        "projects_by_id": projects_by_id,
        "periods": periods,
        "selected_period": selected_period,
    }


@router.get("/intelligence")
def intelligence(request: Request, error: str | None = None, info: str | None = None,
                 period: str | None = None, db: Session = Depends(get_db)):
    period_end = date.fromisoformat(period) if period else None
    context = _screen_context(db, period_end)
    context["recommend_failed"] = error == "recommend_failed"
    context["no_candidates"] = error == "no_candidates"
    context["not_significant"] = error == "not_significant"
    context["recommendation_unchanged"] = info == "recommendation_unchanged"
    return templates.TemplateResponse(request, "intelligence.html", context)


@router.post("/intelligence/recommend")
def recommend(request: Request, market: str = Form(...), brand: str = Form(...),
             period: str | None = Form(None), db: Session = Depends(get_db)):
    # Scoped to the same period the comparison was shown for — a recommendation
    # must be about the numbers the producer actually saw, not silently
    # recomputed from every period's data pooled together.
    query = db.query(CreativeInsight)
    if period:
        query = query.filter(CreativeInsight.period_end == date.fromisoformat(period))
    insights = query.all()
    comparisons = compute_market_comparisons(insights)
    match = next((c for c in comparisons if c["market"] == market), None)
    if match is None:
        return RedirectResponse(url="/intelligence?error=recommend_failed", status_code=303)
    # REVIEW_02.md P6.2: "a significance threshold" only has teeth if the route
    # enforces it too, not just the template hiding the button — the template's
    # control is advisory, same principle as every other capacity/lead-time guard
    # in this app.
    if not match["significant"]:
        return RedirectResponse(url="/intelligence?error=not_significant", status_code=303)

    # REVIEW_02.md P4: dismissed or already-actioned is terminal — the template
    # stops offering the control once accepted or dismissed, and a raw POST must be
    # refused the same way. A pending recommendation is NOT terminal: same as
    # resources.py's conflicts, the control stays available and a repeat request is
    # handled by the dedup check below (returns the existing one unchanged, or
    # replaces it if the underlying facts actually moved) rather than blocked.
    current_status = compute_insight_status(db, market)
    if current_status["status"] in ("actioned", "dismissed"):
        return RedirectResponse(url="/intelligence?error=recommend_failed", status_code=303)

    facts = dict(match)
    facts["brand"] = brand

    existing = (
        db.query(Recommendation)
        .filter_by(kind=RecommendationKind.production_action, status=RecommendationStatus.pending)
        .all()
    )
    existing_for_market = next(
        (r for r in existing if json.loads(r.computed_facts_json).get("market") == market), None)
    if existing_for_market is not None and json.loads(existing_for_market.computed_facts_json) == facts:
        return RedirectResponse(url="/intelligence?info=recommendation_unchanged", status_code=303)

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

    if existing_for_market is not None:
        db.delete(existing_for_market)
        db.flush()

    db.add(Recommendation(
        kind=RecommendationKind.production_action,
        project_id=None,
        payload_json=rec.model_dump_json(),
        rationale=rec.recommended_action,
        computed_facts_json=json.dumps(facts, default=str),
    ))
    db.commit()

    return RedirectResponse(url="/intelligence", status_code=303)


@router.post("/intelligence/{market}/dismiss")
def dismiss(market: str, reason: str = Form(""), db: Session = Depends(get_db)):
    if not reason.strip():
        return RedirectResponse(url="/intelligence?error=recommend_failed", status_code=303)
    dismiss_market_insight(db, market, reason.strip())
    return RedirectResponse(url="/intelligence", status_code=303)
