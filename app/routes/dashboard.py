from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import Localisation, LocalisationStatus, Project, ProjectStatus
from app.services.ai.risk import assess_portfolio_attention
from app.services.attention import build_attention_snapshot
from app.services.capacity import all_person_capacities
from app.services.localisation_risk import summarize_by_market

router = APIRouter()


@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    projects = db.query(Project).all()

    snapshot = build_attention_snapshot(db, on_date=today)
    attention = assess_portfolio_attention(snapshot)
    snapshot_by_project_id = {entry["project_id"]: entry for entry in snapshot}

    at_risk_ids = {
        pid for pid, entry in snapshot_by_project_id.items()
        if entry["cause"] in ("capacity", "localisation", "deadline")
    }
    blocked_ids = {
        pid for pid, entry in snapshot_by_project_id.items()
        if entry["cause"] == "brief"
    }

    active_projects = [p for p in projects if p.status != ProjectStatus.delivered]
    at_risk_projects = [p for p in active_projects if p.id in at_risk_ids]
    blocked_projects = [p for p in active_projects if p.id in blocked_ids]
    on_track_projects = [
        p for p in active_projects if p.id not in at_risk_ids and p.id not in blocked_ids
    ]

    upcoming_deadlines = sorted(
        (p for p in active_projects if today <= p.deadline <= today + timedelta(days=7)),
        key=lambda p: p.deadline,
    )

    capacities = all_person_capacities(db, on_date=today)
    overloaded_count = sum(1 for c in capacities if c.status == "overloaded")
    tight_count = sum(1 for c in capacities if c.status == "tight")
    available_count = sum(1 for c in capacities if c.status == "available")
    total_people = len(capacities)
    total_capacity = sum(c.person.capacity_pct for c in capacities) or 1
    total_allocated = sum(c.allocated_pct for c in capacities)
    aggregate_utilisation = round(100 * total_allocated / total_capacity)

    localisation_rows = db.query(Localisation).all()
    loc_total = len(localisation_rows)
    loc_approved = sum(1 for l in localisation_rows if l.status == LocalisationStatus.approved)
    loc_pct = round(100 * loc_approved / loc_total) if loc_total else 0
    # FEEDBACK_LOG.md A2: the tile names the bottleneck instead of counting rows.
    # Risk-carrying markets first, then busiest, capped so the line stays readable.
    market_summaries = summarize_by_market(db, on_date=today)[:3]

    return templates.TemplateResponse(request, "dashboard.html", {
        "active_count": len(active_projects),
        "on_track_count": len(on_track_projects),
        "at_risk_count": len(at_risk_projects),
        "blocked_count": len(blocked_projects),
        "upcoming_deadlines": upcoming_deadlines,
        "overloaded_count": overloaded_count,
        "tight_count": tight_count,
        "available_count": available_count,
        "total_people": total_people,
        "aggregate_utilisation": aggregate_utilisation,
        "loc_total": loc_total,
        "loc_approved": loc_approved,
        "loc_pct": loc_pct,
        "market_summaries": market_summaries,
        "attention": attention,
    })
