"""Builds the deterministic snapshot that assess_portfolio_attention narrates.
Python decides which projects qualify and why — the model only writes the
prose. See AI_WORKFLOWS.md function 2 and PRODUCT_SPEC.md's dashboard panel.

Causes use four canonical tags per FEEDBACK_LOG.md A3: capacity, deadline,
brief, localisation. Every attention item carries one.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    BriefAnalysis,
    Localisation,
    LocalisationStatus,
    Project,
    ProjectPhase,
    ProjectPhaseStatus,
    ProjectStatus,
)
from app.services.assumptions import get_value
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


# REVIEW_02.md P6.3: "derive the Blocked tile" from the four sources it names.
# Deliberately separate from build_attention_snapshot above — "at risk" is about
# deadline exposure, "blocked" is about work that structurally cannot move right
# now. A project can be both; each function is scoped to its own question.
BLOCKED_STALLED_LOC_STATUSES = (
    LocalisationStatus.in_translation, LocalisationStatus.in_review, LocalisationStatus.qa,
)


def build_blocked_snapshot(db: Session, on_date: date | None = None) -> list[dict]:
    on_date = on_date or date.today()
    projects_by_id = {p.id: p for p in db.query(Project).all()}
    snapshot: list[dict] = []
    seen: set[int] = set()

    # 1. waiting_on_client beyond the agreed review window. Project.updated_at is
    # the only record of when the status last changed (no separate status-history
    # table exists) — a fair proxy since nothing else in this app writes to a
    # project row between pipeline status changes. Assumption only fetched when
    # there's a waiting_on_client project to judge, same guarded-fetch pattern as
    # app/routes/dashboard.py's client_review_minimum_days — a DB with no
    # Assumption rows (most unit-test fixtures) never needs this key.
    waiting_projects = [p for p in projects_by_id.values() if p.status == ProjectStatus.waiting_on_client]
    review_window_days = get_value(db, "client_review_days") if waiting_projects else None
    for project in waiting_projects:
        waiting_since = project.updated_at.date()
        if (on_date - waiting_since).days <= review_window_days:
            continue
        seen.add(project.id)
        snapshot.append({
            "project_id": project.id,
            "project_name": project.name,
            "cause": "waiting_on_client",
            "detail": (
                f"waiting on client since {waiting_since.strftime('%d %b')}, "
                f"beyond the {review_window_days:g}-day review window"
            ),
            "suggested_screen": "pipeline",
        })

    # 2. Brief below readiness threshold and past its intended start date. There is
    # no stored "intended start date" — deadline minus the brief's own estimated
    # duration is the honest proxy: the date work would need to have started to
    # land on time.
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
        if project.estimated_days is None:
            continue
        intended_start = project.deadline - timedelta(days=round(project.estimated_days))
        if on_date < intended_start:
            continue
        seen.add(project.id)
        snapshot.append({
            "project_id": project.id,
            "project_name": project.name,
            "cause": "brief_stalled",
            "detail": (
                f"brief readiness {analysis.readiness_score}%, below the "
                f"{settings.brief_readiness_threshold}% threshold, past its "
                f"{intended_start.strftime('%d %b')} intended start"
            ),
            "suggested_screen": "brief",
        })

    # 3. Localisation stalled with no translator assigned — a structural stall,
    # not a deadline-window check (that's get_localisation_risks, used above for
    # the "at risk" cause).
    stalled_loc = (
        db.query(Localisation)
        .filter(
            Localisation.status.in_(BLOCKED_STALLED_LOC_STATUSES),
            Localisation.translator_id.is_(None),
        )
        .all()
    )
    for row in stalled_loc:
        project = projects_by_id.get(row.project_id)
        if project is None or project.id in seen:
            continue
        seen.add(project.id)
        snapshot.append({
            "project_id": project.id,
            "project_name": project.name,
            "cause": "localisation_stalled",
            "detail": f"{row.target_market} localisation has no translator assigned",
            "suggested_screen": "localisation",
        })

    # 4. A scheduled phase that has started with nobody assigned. Milestones and
    # phases with no required_roles (e.g. an internal-only checkpoint) don't need
    # a person, so they're excluded rather than flagged as unstaffed.
    started_unstaffed = (
        db.query(ProjectPhase)
        .filter(
            ProjectPhase.start_date <= on_date,
            ProjectPhase.status != ProjectPhaseStatus.complete,
            ProjectPhase.assigned_person_id.is_(None),
            ProjectPhase.is_milestone.is_(False),
            ProjectPhase.required_roles != "",
        )
        .all()
    )
    for phase in started_unstaffed:
        project = projects_by_id.get(phase.project_id)
        if project is None or project.id in seen:
            continue
        seen.add(project.id)
        snapshot.append({
            "project_id": project.id,
            "project_name": project.name,
            "cause": "unstaffed_phase",
            "detail": f"'{phase.name}' started {phase.start_date.strftime('%d %b')} with nobody assigned",
            "suggested_screen": "timeline",
        })

    return snapshot
