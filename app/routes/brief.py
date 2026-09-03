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
    ProjectType,
)
from app.services.ai.brief import analyse_brief
from app.services.ai.estimate import quick_estimate
from app.services.ai.schemas import BriefExtraction
from app.services.assumptions import get_text_value, get_value
from app.services.brief import RUBRIC_BLOCKS, RUBRIC_WEIGHTS, score_readiness
from app.services.estimate import (
    PRODUCTION_SCALE_LABELS,
    PRODUCTION_SCALE_TIER_ORDER,
    PROJECT_TYPE_TO_WORK_TYPE,
    TERRITORY_LABELS,
    TERRITORY_ORDER,
    compute_estimate,
    compute_production_cost,
    dominant_cost_component,
    infer_brand_count,
    infer_original_photography,
    infer_production_scale,
    infer_territory,
)
from app.services.project_creation import finalize_project, resolve_project_type_id

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


def _compute_estimate_block(db: Session, *, work_type: str, asset_count: int,
                            original_photography: bool, review_rounds: int, confidence: str,
                            target_market_count: int, localisation_required: bool,
                            production_scale: str | None, territory: str | None,
                            brand_count: int) -> dict:
    """REVIEW_03.md R4: the one calculation both estimate paths share — Quick
    Estimate and the Full Brief Assistant each infer these inputs their own way
    (regex on raw text vs. an AI-extracted BriefExtraction), but both hand them
    to this exact function, so the two screens can never disagree about what a
    given shape of work costs."""
    try:
        computed = compute_estimate(
            db, work_type=work_type, asset_count=asset_count,
            original_photography=original_photography, review_rounds=review_rounds,
            target_market_count=target_market_count, localisation_required=localisation_required,
            confidence=confidence,
        )
    except ValueError:
        computed = None

    # External production spend only exists once a shoot is confirmed —
    # production_scale/territory are explicit dropdowns (pre-filled by
    # best-effort inference, never trusted on their own) so a producer's own
    # choice always overrides a wrong guess before it reaches this number.
    production = None
    dominant_statement = None
    coverage_note = None
    if original_photography and production_scale and territory:
        try:
            production = compute_production_cost(
                db, scale_tier=production_scale, territory=territory, brand_count=brand_count,
            )
        except ValueError:
            production = None
        if production is not None and computed is not None:
            dominant_statement = dominant_cost_component(computed.cost_high, production)
        if production is not None:
            try:
                coverage_note = get_text_value(db, "production_cost_coverage_note")
            except ValueError:
                coverage_note = None

    return {
        "computed": computed, "production": production,
        "dominant_statement": dominant_statement, "coverage_note": coverage_note,
    }


def _estimate_editable_context(*, work_type: str, asset_count: int, original_photography: bool,
                               review_rounds: int, confidence: str, production_scale: str | None,
                               territory: str | None, brand_count: int, block: dict) -> dict:
    """The editable inputs plus dropdown vocabulary both recompute forms render —
    factored out so Quick Estimate and the Full Brief Assistant build an
    identical shape rather than two independently-maintained lookalikes."""
    return {
        "work_type": work_type,
        "asset_count": asset_count,
        "original_photography": original_photography,
        "review_rounds": review_rounds,
        "confidence": confidence,
        "production_scale": production_scale,
        "territory": territory,
        "brand_count": brand_count,
        "production_scale_tiers": PRODUCTION_SCALE_TIER_ORDER,
        "production_scale_labels": PRODUCTION_SCALE_LABELS,
        "territories": TERRITORY_ORDER,
        "territory_labels": TERRITORY_LABELS,
        **block,
    }


def _quick_estimate_context(db: Session, *, raw_text: str, work_type: str, markets: list[str],
                            localisation_required: bool, single_best_question: str,
                            caveats: list[str], inferred_volume: int, volume_confidence: str,
                            asset_count: int, original_photography: bool, review_rounds: int,
                            confidence: str, production_scale: str | None = None,
                            territory: str | None = None, brand_count: int = 1) -> dict:
    target_market_count = len(markets) if localisation_required else 0
    block = _compute_estimate_block(
        db, work_type=work_type, asset_count=asset_count,
        original_photography=original_photography, review_rounds=review_rounds,
        confidence=confidence, target_market_count=target_market_count,
        localisation_required=localisation_required, production_scale=production_scale,
        territory=territory, brand_count=brand_count,
    )

    return {
        "brands": BRANDS,
        "mode": "quick",
        "confidence_bands": CONFIDENCE_BANDS,
        "raw_text": raw_text,
        "markets": markets,
        "markets_json": json.dumps(markets),
        "localisation_required": localisation_required,
        "single_best_question": single_best_question,
        "caveats": caveats,
        "caveats_json": json.dumps(caveats),
        "inferred_volume": inferred_volume,
        "volume_confidence": volume_confidence,
        **_estimate_editable_context(
            work_type=work_type, asset_count=asset_count,
            original_photography=original_photography, review_rounds=review_rounds,
            confidence=confidence, production_scale=production_scale, territory=territory,
            brand_count=brand_count, block=block,
        ),
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
    production_scale = by_key.get("production_scale")
    territory = by_key.get("territory")
    brand_count = int(by_key.get("brand_count", 1))

    context = _quick_estimate_context(
        db, raw_text=raw_text, work_type=estimate.work_type, markets=estimate.markets,
        localisation_required=estimate.localisation_required,
        single_best_question=estimate.single_best_question, caveats=estimate.caveats,
        inferred_volume=estimate.inferred_volume, volume_confidence=estimate.volume_confidence,
        asset_count=asset_count, original_photography=original_photography,
        review_rounds=review_rounds, confidence=estimate.confidence,
        production_scale=production_scale, territory=territory, brand_count=brand_count,
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
    confidence: str = Form(...), production_scale: str | None = Form(None),
    territory: str | None = Form(None), brand_count: int = Form(1),
    db: Session = Depends(get_db),
):
    context = _quick_estimate_context(
        db, raw_text=raw_text, work_type=work_type, markets=json.loads(markets_json),
        localisation_required=localisation_required, single_best_question=single_best_question,
        caveats=json.loads(caveats_json), inferred_volume=inferred_volume,
        volume_confidence=volume_confidence, asset_count=asset_count,
        original_photography=original_photography, review_rounds=review_rounds,
        confidence=confidence, production_scale=production_scale, territory=territory,
        brand_count=brand_count,
    )
    return templates.TemplateResponse(request, "brief.html", context)


def _confidence_band_for_score(score: int) -> str:
    """REVIEW_03.md R4 commit 2: the Full Brief Assistant has no confidence
    concept of its own — the readiness score already answers the same
    question ('how much of this is stated vs. guessed'), so it's reused
    rather than inventing a second scale."""
    if score >= 85:
        return "high"
    if score >= 70:
        return "medium"
    if score >= 50:
        return "low_medium"
    return "low"


def _infer_full_brief_estimate_inputs(db: Session, extraction: BriefExtraction, raw_text: str) -> dict:
    """Same estimate inputs Quick Estimate infers, derived from the richer
    signal a full extraction already has — markets come from the AI extraction
    itself rather than a fresh regex pass, and work_type from the same
    deliverable -> ProjectType resolution project creation already uses."""
    text = raw_text.lower()
    deliverable_types = {d.type for d in extraction.deliverables if d.type}
    project_type_id = resolve_project_type_id(db, deliverable_types)
    work_type = "social"
    if project_type_id is not None:
        project_type = db.get(ProjectType, project_type_id)
        if project_type is not None:
            work_type = PROJECT_TYPE_TO_WORK_TYPE.get(project_type.name, "social")

    asset_count = sum(d.quantity or 1 for d in extraction.deliverables) or 6
    original_photography, _ = infer_original_photography(text)
    try:
        # Unlike Quick Estimate, the Full Brief Assistant had no dependency on
        # the Assumption table before this — a fresh/unseeded database must
        # still render extraction and the readiness score even though the new
        # estimate block can't. 2 matches ASSUMPTIONS.md's own seeded default.
        review_rounds = int(get_value(db, "default_review_rounds"))
    except ValueError:
        review_rounds = 2

    production_scale = territory = None
    brand_count = 1
    if original_photography:
        production_scale, _ = infer_production_scale(text)
        territory, _ = infer_territory(extraction.markets, text)
        brand_count, _ = infer_brand_count(text)

    return {
        "work_type": work_type, "asset_count": asset_count,
        "original_photography": original_photography, "review_rounds": review_rounds,
        "production_scale": production_scale, "territory": territory, "brand_count": brand_count,
    }


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

    # REVIEW_03.md R4 commit 2: a cost estimate on the Full Brief path at all —
    # it had none before. target_market_count/localisation_required come
    # straight from the extraction, same as create-project's own reading of it.
    estimate_inputs = _infer_full_brief_estimate_inputs(db, extraction, raw_text)
    confidence = _confidence_band_for_score(result.score)
    block = _compute_estimate_block(
        db, confidence=confidence,
        target_market_count=len(extraction.localisation.targets) if extraction.localisation.required else 0,
        localisation_required=extraction.localisation.required,
        **estimate_inputs,
    )

    return templates.TemplateResponse(request, "brief.html", {
        "brands": BRANDS,
        "mode": "full",
        "confidence_bands": CONFIDENCE_BANDS,
        "raw_text": raw_text,
        "extraction": extraction,
        "result": result,
        "rubric_weights": RUBRIC_WEIGHTS,
        "rubric_blocks": RUBRIC_BLOCKS,
        "analysis_id": analysis.id,
        "suggested_name": (extraction.objective or "New project")[:60],
        **_estimate_editable_context(**estimate_inputs, confidence=confidence, block=block),
    })


@router.post("/brief/analyse/recompute-estimate")
def analyse_recompute_estimate(
    request: Request, analysis_id: int = Form(...),
    work_type: str = Form(...), asset_count: int = Form(...),
    original_photography: bool = Form(False), review_rounds: int = Form(...),
    confidence: str = Form(...), production_scale: str | None = Form(None),
    territory: str | None = Form(None), brand_count: int = Form(1),
    db: Session = Depends(get_db),
):
    """The Full Brief Assistant's own 'Recalculate' — no new AI call, same as
    Quick Estimate's recompute. Re-derives extraction/result from the stored
    analysis rather than trusting a stale readiness_score column (REVIEW_03.md
    R5.1 is exactly this failure mode for the score; reading raw_text and
    extracted_json fresh here means this route can't repeat it)."""
    analysis = db.get(BriefAnalysis, analysis_id)
    if analysis is None:
        return templates.TemplateResponse(request, "brief.html", {
            "brands": BRANDS, "mode": "full", "ai_failed": True,
        })

    extraction = BriefExtraction.model_validate_json(analysis.extracted_json)
    result = score_readiness(extraction)

    block = _compute_estimate_block(
        db, work_type=work_type, asset_count=asset_count,
        original_photography=original_photography, review_rounds=review_rounds,
        confidence=confidence,
        target_market_count=len(extraction.localisation.targets) if extraction.localisation.required else 0,
        localisation_required=extraction.localisation.required,
        production_scale=production_scale, territory=territory, brand_count=brand_count,
    )

    return templates.TemplateResponse(request, "brief.html", {
        "brands": BRANDS,
        "mode": "full",
        "confidence_bands": CONFIDENCE_BANDS,
        "raw_text": analysis.raw_text,
        "extraction": extraction,
        "result": result,
        "rubric_weights": RUBRIC_WEIGHTS,
        "rubric_blocks": RUBRIC_BLOCKS,
        "analysis_id": analysis.id,
        "suggested_name": (extraction.objective or "New project")[:60],
        **_estimate_editable_context(
            work_type=work_type, asset_count=asset_count,
            original_photography=original_photography, review_rounds=review_rounds,
            confidence=confidence, production_scale=production_scale, territory=territory,
            brand_count=brand_count, block=block,
        ),
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
