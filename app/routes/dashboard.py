from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import Localisation, LocalisationStatus, Project, ProjectPhase, ProjectStatus
from app.services.ai.feasibility import assess_schedule_feasibility
from app.services.ai.risk import assess_portfolio_attention
from app.services.assumptions import get_value
from app.services.attention import build_attention_snapshot
from app.services.capacity import aggregate_utilisation_pct, all_person_capacities
from app.services.localisation_risk import summarize_by_market
from app.services.scheduling import build_feasibility_facts

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
    aggregate_utilisation = aggregate_utilisation_pct(capacities)

    localisation_rows = db.query(Localisation).all()
    loc_total = len(localisation_rows)
    loc_approved = sum(1 for l in localisation_rows if l.status == LocalisationStatus.approved)
    loc_pct = round(100 * loc_approved / loc_total) if loc_total else 0
    # FEEDBACK_LOG.md A2: the tile names the bottleneck instead of counting rows.
    # Risk-carrying markets first, then busiest, capped so the line stays readable.
    market_summaries = summarize_by_market(db, on_date=today)[:3]

    # assess_schedule_feasibility (Session B step 6) — only scheduled projects that don't
    # fit their deadline get an assessment; a feasible schedule has nothing to narrate.
    # client_review_minimum_days is read live from Assumption (DECISIONS.md 027) — only
    # fetched when there's at least one scheduled project, so a dashboard with none never
    # depends on the Assumption table being seeded.
    scheduled_ids = [row[0] for row in db.query(ProjectPhase.project_id).distinct().all()]
    schedule_alerts = []
    if scheduled_ids:
        client_review_minimum_days = int(get_value(db, "client_review_minimum_days"))
        for pid in scheduled_ids:
            project = next((p for p in projects if p.id == pid), None)
            if project is None:
                continue
            phases = db.query(ProjectPhase).filter_by(project_id=pid).all()
            facts = build_feasibility_facts(phases, project.deadline, today=today,
                                            client_review_minimum_days=client_review_minimum_days)
            if facts.get("feasible", True):
                continue
            schedule_alerts.append({
                "project": project,
                "assessment": assess_schedule_feasibility(facts),
            })
        schedule_alerts.sort(key=lambda a: a["project"].deadline)

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
        "schedule_alerts": schedule_alerts,
    })
