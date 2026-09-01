"""REVIEW_03.md R6: a project must arrive complete regardless of which screen
created it — a type, an estimate, its deliverables, its localisation rows, and
(where a type could be resolved) a generated schedule. Before this module
existed, app/routes/recommendations.py's production-action accept set
project_type_id and estimated_days, but app/routes/brief.py's Full Brief flow
never did — so a project created from the Brief Assistant could never generate
a schedule, could never appear on /timeline, and could never be caught by
app/services/attention.py's build_blocked_snapshot brief-stalled check, which
skips any project with estimated_days is None. REVIEW_03.md's own R1 audit
traced the "Timeline shows 7 of 12 projects" and part of the "0 at risk
alongside 5 blocked" symptoms to this gap.

Call finalize_project() once, immediately after `db.add(project); db.flush()`,
from every code path that creates a Project. It is deliberately narrow: it
does not touch Assignment rows (a phase-derived candidate list is already
live-computed once phases exist — DECISIONS.md 021 — and a caller-specific
"who's assigned" decision, like recommendations.py's suggested person, stays
in that caller), and it does not touch Project.volume_factor (deriving one
from deliverable count needs an asset-count concept the Full Brief flow
doesn't currently ask for — a separate, undecided question, left at the
model's existing default of 1.0 rather than guessed at here).
"""

from sqlalchemy.orm import Session

from app.models import (
    Deliverable,
    DeliverableStatus,
    DeliverableType,
    Localisation,
    LocalisationStatus,
    Project,
    ProjectPhase,
    ProjectType,
    SubStatus,
)
from app.services.scheduling import generate_schedule

# Deliverable type -> ProjectType name. Was app/routes/recommendations.py's
# private _PROJECT_TYPE_BY_DELIVERABLE — moved here now that it has a second
# caller. Covers every DeliverableType the schema defines, not just the ones
# reachable from any one path today.
PROJECT_TYPE_BY_DELIVERABLE = {
    "social_static": "Social / AI-generated content",
    "social_video": "Social / AI-generated content",
    "motion": "Film / branded content",
    "paid_display": "Stills",
    "homepage_banner": "Stills",
    "email": "Stills",
}


def resolve_project_type_id(db: Session, deliverable_types: set[str]) -> int | None:
    """First deliverable type with a known mapping wins (matches
    recommendations.py's pre-existing behaviour). None if no deliverable maps
    to a type, or that ProjectType hasn't been seeded — both are honest "we
    don't know" states, not errors: a project with no resolvable type simply
    can't generate a schedule yet, same as today."""
    type_name = next(
        (PROJECT_TYPE_BY_DELIVERABLE[t] for t in deliverable_types if t in PROJECT_TYPE_BY_DELIVERABLE),
        None,
    )
    if type_name is None:
        return None
    project_type = db.query(ProjectType).filter_by(name=type_name).first()
    return project_type.id if project_type is not None else None


def estimate_days_for_schedule(phases: list[ProjectPhase]) -> float | None:
    """Calendar days from the schedule's earliest phase start to its latest
    phase end — the same quantity app/services/attention.py's
    build_blocked_snapshot already assumes this field means when it computes
    `deadline - timedelta(days=estimated_days)` as a project's intended start.
    Deriving it from the schedule that was just generated, rather than a
    separate estimate, means the two can't disagree by construction."""
    if not phases:
        return None
    earliest_start = min(p.start_date for p in phases)
    latest_end = max(p.end_date for p in phases)
    return float((latest_end - earliest_start).days)


def finalize_project(
    db: Session,
    project: Project,
    *,
    deliverables: list[dict],
    localisation_targets: list[str],
) -> Project:
    """Guarantees deliverables, localisation rows, a project type where one is
    resolvable, and — only then — a generated schedule and an estimate.
    `deliverables` is a list of {"type", "market", "format_spec"} dicts (market
    and format_spec optional, falling back to project.source_market and None).
    Does not overwrite a project_type_id or estimated_days the caller already
    set (recommendations.py's production-action accept supplies its own
    estimate from the mock's own quantity-based figure; nothing should
    silently discard a better number for this module's generic fallback)."""
    deliverable_types = {d["type"] for d in deliverables if d.get("type")}

    for d in deliverables:
        if d.get("type") in DeliverableType.__members__:
            db.add(Deliverable(
                project_id=project.id,
                type=DeliverableType(d["type"]),
                market=d.get("market") or project.source_market,
                format_spec=d.get("format_spec"),
                status=DeliverableStatus.not_started,
                deadline=project.deadline,
            ))

    for target in localisation_targets:
        db.add(Localisation(
            project_id=project.id,
            target_market=target,
            language=target.lower(),
            translator_id=None,
            status=LocalisationStatus.not_started,
            review_status=SubStatus.pending,
            qa_status=SubStatus.pending,
            due_date=project.deadline,
        ))

    if project.project_type_id is None:
        project.project_type_id = resolve_project_type_id(db, deliverable_types)

    db.flush()

    if project.project_type_id is not None:
        phases = generate_schedule(db, project)
        if project.estimated_days is None:
            project.estimated_days = estimate_days_for_schedule(phases)

    return project
