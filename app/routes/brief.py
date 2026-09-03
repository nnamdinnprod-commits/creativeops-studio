import json
import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import (
    BriefAnalysis,
    Person,
    PersonRole,
    Priority,
    Project,
    ProjectStatus,
)
from app.services.ai.brief import analyse_brief
from app.services.ai.estimate import quick_estimate
from app.services.ai.schemas import BriefExtraction
from app.services.brief import RUBRIC_BLOCKS, RUBRIC_WEIGHTS, score_readiness
from app.services.estimate import compute_estimate
from app.services.project_creation import finalize_project

router = APIRouter()

BRANDS = ["Fotomera", "Halveth", "Cassenvale"]
CONFIDENCE_BANDS = ["high", "medium", "low_medium", "low"]
_WEEKDAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def resolve_deadline(deadline_text: str | None) -> tuple[date, bool]:
    """Returns (deadline, was_confirmed). Falls back to a 14-day placeholder when
    the extracted deadline text can't be resolved to an actual date — the project
    still needs a deadline value (DATA_MODEL.md: non-nullable), but an unresolved
    one is not treated as confirmed for scoring or display purposes."""
    if deadline_text:
        try:
            return date.fromisoformat(deadline_text), True
        except ValueError:
            pass
        match = re.search(r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
                          deadline_text.lower())
        if match:
            target_idx = _WEEKDAY_NAMES.index(match.group(1))
            today = date.today()
            days_ahead = (target_idx - today.weekday()) % 7 or 7
            return today + timedelta(days=days_ahead), True
    return date.today() + timedelta(days=14), False


@router.get("/brief")
def brief_form(request: Request, mode: str = "quick"):
    return templates.TemplateResponse(request, "brief.html", {
        "brands": BRANDS, "mode": mode, "confidence_bands": CONFIDENCE_BANDS,
    })


def _quick_estimate_context(db: Session, *, raw_text: str, work_type: str, markets: list[str],
                            localisation_required: bool, single_best_question: str,
                            caveats: list[str], inferred_volume: int, volume_confidence: str,
                            asset_count: int, original_photography: bool, review_rounds: int,
                            confidence: str) -> dict:
    target_market_count = len(markets) if localisation_required else 0
    try:
        computed = compute_estimate(
            db, work_type=work_type, asset_count=asset_count,
            original_photography=original_photography, review_rounds=review_rounds,
            target_market_count=target_market_count, localisation_required=localisation_required,
            confidence=confidence,
        )
    except ValueError:
        computed = None

    return {
        "brands": BRANDS,
        "mode": "quick",
        "confidence_bands": CONFIDENCE_BANDS,
        "raw_text": raw_text,
        "work_type": work_type,
        "markets": markets,
        "markets_json": json.dumps(markets),
        "localisation_required": localisation_required,
        "single_best_question": single_best_question,
        "caveats": caveats,
        "caveats_json": json.dumps(caveats),
        "inferred_volume": inferred_volume,
        "volume_confidence": volume_confidence,
        "asset_count": asset_count,
        "original_photography": original_photography,
        "review_rounds": review_rounds,
        "confidence": confidence,
        "computed": computed,
    }


@router.post("/brief/quick-estimate")
def quick_estimate_analyse(request: Request, raw_text: str = Form(...), db: Session = Depends(get_db)):
    estimate = quick_estimate(raw_text)
    if estimate is None:
        return templates.TemplateResponse(request, "brief.html", {
            "brands": BRANDS, "mode": "quick", "confidence_bands": CONFIDENCE_BANDS,
            "raw_text": raw_text, "ai_failed": True,
        })

    by_key = {a.key: a.value for a in estimate.assumptions}
    asset_count = int(by_key.get("asset_count", estimate.inferred_volume))
    original_photography = bool(by_key.get("original_photography", False))
    review_rounds = int(by_key.get("review_rounds", 2))

    context = _quick_estimate_context(
        db, raw_text=raw_text, work_type=estimate.work_type, markets=estimate.markets,
        localisation_required=estimate.localisation_required,
        single_best_question=estimate.single_best_question, caveats=estimate.caveats,
        inferred_volume=estimate.inferred_volume, volume_confidence=estimate.volume_confidence,
        asset_count=asset_count, original_photography=original_photography,
        review_rounds=review_rounds, confidence=estimate.confidence,
    )
    return templates.TemplateResponse(request, "brief.html", context)


@router.post("/brief/quick-estimate/recompute")
def quick_estimate_recompute(
    request: Request,
    raw_text: str = Form(...), work_type: str = Form(...), markets_json: str = Form(...),
    localisation_required: bool = Form(...), single_best_question: str = Form(...),
    caveats_json: str = Form(...), inferred_volume: int = Form(...),
    volume_confidence: str = Form(...), asset_count: int = Form(...),
    original_photography: bool = Form(False), review_rounds: int = Form(...),
    confidence: str = Form(...), db: Session = Depends(get_db),
):
    context = _quick_estimate_context(
        db, raw_text=raw_text, work_type=work_type, markets=json.loads(markets_json),
        localisation_required=localisation_required, single_best_question=single_best_question,
        caveats=json.loads(caveats_json), inferred_volume=inferred_volume,
        volume_confidence=volume_confidence, asset_count=asset_count,
        original_photography=original_photography, review_rounds=review_rounds,
        confidence=confidence,
    )
    return templates.TemplateResponse(request, "brief.html", context)


@router.post("/brief/analyse")
def analyse(request: Request, raw_text: str = Form(...), db: Session = Depends(get_db)):
    extraction = analyse_brief(raw_text)

    if extraction is None:
        return templates.TemplateResponse(request, "brief.html", {
            "brands": BRANDS,
            "mode": "full",
            "raw_text": raw_text,
            "ai_failed": True,
        })

    result = score_readiness(extraction)

    analysis = BriefAnalysis(
        raw_text=raw_text,
        extracted_json=extraction.model_dump_json(),
        readiness_score=result.score,
        missing_fields_json=json.dumps(result.missing_fields),
        blocking_reasons=json.dumps(result.blocking_reasons),
    )
    db.add(analysis)
    db.commit()

    return templates.TemplateResponse(request, "brief.html", {
        "brands": BRANDS,
        "mode": "full",
        "raw_text": raw_text,
        "extraction": extraction,
        "result": result,
        "rubric_weights": RUBRIC_WEIGHTS,
        "rubric_blocks": RUBRIC_BLOCKS,
        "analysis_id": analysis.id,
        "suggested_name": (extraction.objective or "New project")[:60],
    })


@router.post("/brief/create-project")
def create_project(request: Request, analysis_id: int = Form(...), project_name: str = Form(...),
                   brand: str = Form(...), db: Session = Depends(get_db)):
    analysis = db.get(BriefAnalysis, analysis_id)
    if analysis is None:
        return templates.TemplateResponse(request, "brief.html", {
            "brands": BRANDS,
            "mode": "full",
            "ai_failed": True,
        })

    extraction = BriefExtraction.model_validate_json(analysis.extracted_json)
    deadline, deadline_confirmed = resolve_deadline(extraction.deadline)

    source_market = extraction.localisation.source or (extraction.markets[0] if extraction.markets else "NL")
    owner = db.query(Person).filter_by(role=PersonRole.producer).first()

    project = Project(
        name=project_name,
        brand=brand,
        campaign=project_name,
        source_market=source_market,
        priority=Priority.medium,
        status=ProjectStatus.brief,
        deadline=deadline,
        owner_id=owner.id,
        brief_raw=analysis.raw_text,
        brief_analysis_id=analysis.id,
    )
    db.add(project)
    db.flush()

    # REVIEW_03.md R6: type, estimate, deliverables, localisation rows, and a
    # generated schedule where a type resolves — every project-creation path
    # goes through this now, not just recommendations.py's. Before this, a
    # Brief Assistant project could never generate a schedule, appear on
    # /timeline, or be caught by the Blocked tile's brief-stalled check.
    finalize_project(
        db, project,
        deliverables=[d.model_dump() for d in extraction.deliverables],
        localisation_targets=extraction.localisation.targets if extraction.localisation.required else [],
    )

    analysis.created_project_id = project.id
    db.commit()

    return templates.TemplateResponse(request, "brief.html", {
        "brands": BRANDS,
        "mode": "full",
        "created_project": project,
        "deadline_confirmed": deadline_confirmed,
    })
