"""Builds the deterministic snapshot that assess_portfolio_attention narrates.
Python decides which projects qualify and why — the model only writes the
prose. See AI_WORKFLOWS.md function 2 and PRODUCT_SPEC.md's dashboard panel.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.config import settings
from app.models import BriefAnalysis, Project, ProjectStatus
from app.services.capacity import get_conflicts
from app.services.localisation_risk import get_localisation_risks


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
            "cause": "capacity_conflict",
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
            "cause": "localisation_risk",
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
            "cause": "low_brief_readiness",
            "detail": f"brief readiness {analysis.readiness_score}%, below the {settings.brief_readiness_threshold}% threshold",
            "suggested_screen": "brief",
        })

    return snapshot
