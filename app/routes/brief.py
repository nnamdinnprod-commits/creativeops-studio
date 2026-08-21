import json
import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import (
    BriefAnalysis,
    Deliverable,
    DeliverableStatus,
    DeliverableType,
    Localisation,
    LocalisationStatus,
    Person,
    PersonRole,
    Priority,
    Project,
    ProjectStatus,
    SubStatus,
)
from app.services.ai.brief import analyse_brief
from app.services.ai.schemas import BriefExtraction
from app.services.brief import RUBRIC_BLOCKS, RUBRIC_WEIGHTS, score_readiness

router = APIRouter()

BRANDS = ["Albelli", "Photobox", "Hofmann"]
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
def brief_form(request: Request):
    return templates.TemplateResponse(request, "brief.html", {"brands": BRANDS})


@router.post("/brief/analyse")
def analyse(request: Request, raw_text: str = Form(...), db: Session = Depends(get_db)):
    extraction = analyse_brief(raw_text)

    if extraction is None:
        return templates.TemplateResponse(request, "brief.html", {
            "brands": BRANDS,
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
        localisation_required=extraction.localisation.required,
        estimated_days=None,
    )
    db.add(project)
    db.flush()

    for d in extraction.deliverables:
        if d.type and d.type in DeliverableType.__members__:
            db.add(Deliverable(
                project_id=project.id,
                type=DeliverableType(d.type),
                market=d.market or source_market,
                format_spec=d.format_spec,
                status=DeliverableStatus.not_started,
                deadline=deadline,
            ))

    if extraction.localisation.required:
        for target in extraction.localisation.targets:
            db.add(Localisation(
                project_id=project.id,
                target_market=target,
                language=target.lower(),
                translator_id=None,
                status=LocalisationStatus.not_started,
                review_status=SubStatus.pending,
                qa_status=SubStatus.pending,
                due_date=deadline,
            ))

    analysis.created_project_id = project.id
    db.commit()

    return templates.TemplateResponse(request, "brief.html", {
        "brands": BRANDS,
        "created_project": project,
        "deadline_confirmed": deadline_confirmed,
    })
