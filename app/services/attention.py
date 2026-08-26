"""Builds the deterministic snapshot that assess_portfolio_attention narrates.
Python decides which projects qualify and why — the model only writes the
prose. See AI_WORKFLOWS.md function 2 and PRODUCT_SPEC.md's dashboard panel.

Causes use four canonical tags per FEEDBACK_LOG.md A3: capacity, deadline,
brief, localisation. Every attention item carries one.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import BriefAnalysis, Project, ProjectStatus
from app.services.capacity import get_conflicts
from app.services.localisation_risk import get_localisation_risks

DEADLINE_WINDOW_WORKING_DAYS = 7

# FEEDBACK_LOG.md A3 asks to flag a project "behind where the schedule implies
# it should be" — that concept needs the phase/schedule system from Session 2
# (PLANNING.md), which doesn't exist yet. Proxy until then: still in an early
# pipeline stage this close to its deadline is a fair, honest substitute using
# only what V1 actually has.
EARLY_STATUSES = (ProjectStatus.brief, ProjectStatus.ready, ProjectStatus.assigned)


def _add_working_days(start: date, working_days: int) -> date:
    d = start
    counted = 0
    while counted < working_days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            counted += 1
    return d


def build_attention_snapshot(db: Session, on_date: date | None = None) -> list[dict]:
    on_date = on_date or date.today()
    projects_by_id = {p.id: p for p in db.query(Project).all()}
    snapshot: list[dict] = []
    seen: set[int] = set()

    for conflict in get_conflicts(db, on_date):
        project = min(conflict.projects, key=lambda p: p.deadline)
        if project.id in seen:
            continue
        seen.add(project.id)
        snapshot.append({
            "project_id": project.id,
            "project_name": project.name,
            "severity": "high",
            "cause": "capacity",
            "detail": (
                f"{conflict.person.name} is at {conflict.allocated_pct}% allocation "
                f"against a {project.deadline.strftime('%A %d %b')} deadline"
            ),
            "suggested_screen": "resources",
        })

    for flag in get_localisation_risks(db, on_date):
        project = projects_by_id.get(flag.localisation.project_id)
        if project is None or project.id in seen:
            continue
        seen.add(project.id)
        snapshot.append({
            "project_id": project.id,
            "project_name": project.name,
            "severity": "high" if flag.days_to_due <= 4 else "medium",
            "cause": "localisation",
            "detail": flag.reason,
            "suggested_screen": "pipeline",
        })

    low_readiness = (
        db.query(BriefAnalysis)
        .filter(
            BriefAnalysis.readiness_score < settings.brief_readiness_threshold,
            BriefAnalysis.created_project_id.isnot(None),
        )
        .all()
    )
    for analysis in low_readiness:
        project = projects_by_id.get(analysis.created_project_id)
        if project is None or project.id in seen:
            continue
        if project.status not in (ProjectStatus.brief, ProjectStatus.ready):
            continue
        seen.add(project.id)
        snapshot.append({
            "project_id": project.id,
            "project_name": project.name,
            "severity": "medium",
            "cause": "brief",
            "detail": f"brief readiness {analysis.readiness_score}%, below the {settings.brief_readiness_threshold}% threshold",
            "suggested_screen": "brief",
        })

    deadline_cutoff = _add_working_days(on_date, DEADLINE_WINDOW_WORKING_DAYS)
    for project in projects_by_id.values():
        if project.id in seen:
            continue
        if project.status not in EARLY_STATUSES:
            continue
        if not (on_date <= project.deadline <= deadline_cutoff):
            continue
        seen.add(project.id)
        snapshot.append({
            "project_id": project.id,
            "project_name": project.name,
            "severity": "high",
            "cause": "deadline",
            "detail": (
                f"deadline is {project.deadline.strftime('%A %d %b')} and status is still "
                f"{project.status.value.replace('_', ' ')}"
            ),
            "suggested_screen": "pipeline",
        })

    return snapshot
