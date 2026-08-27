"""docs/PLANNING.md 'Back-scheduling'. Deterministic — dates and day-counts are computed
here, never by the model. back_schedule() is a pure function over PhaseTemplate rows;
generate_schedule() is the Session B step 3 addition that persists its output as ProjectPhase
rows for one project."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import PhaseKind, PhaseTemplate, Project, ProjectPhase, ProjectPhaseStatus

# docs/ASSUMPTIONS.md "Review and approval cycles". Session C builds the editable Assumption
# table; until then this is the fixed value that table would otherwise hold.
CLIENT_REVIEW_DAYS = 3
CLIENT_REVIEW_MINIMUM_DAYS = 2

# docs/ASSUMPTIONS.md "Volume scaling" — deliberately sub-linear, setup cost is fixed.
VOLUME_SCALE_BANDS: list[tuple[int, int, float]] = [
    (1, 6, 1.0),
    (7, 15, 1.6),
    (16, 30, 2.5),
    (31, 60, 3.8),
]


def volume_factor_for(asset_count: int) -> float:
    for low, high, factor in VOLUME_SCALE_BANDS:
        if low <= asset_count <= high:
            return factor
    raise ValueError(f"asset_count {asset_count} is outside the supported 1-60 range")


def _working_day_before(from_date: date) -> date:
    step = from_date - timedelta(days=1)
    while step.weekday() >= 5:  # Saturday=5, Sunday=6
        step -= timedelta(days=1)
    return step


def _working_days_before(from_date: date, count: int) -> date:
    """`from_date` itself if count is 0, otherwise the date `count` working days earlier."""
    current = from_date
    for _ in range(count):
        current = _working_day_before(current)
    return current


def working_days_after(from_date: date, count: int) -> date:
    """`from_date` itself if count is 0, otherwise the date `count` working days later."""
    current = from_date
    remaining = count
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _working_days_in_range(start: date, end: date) -> int:
    """Weekdays from start to end inclusive — used for a persisted ProjectPhase, which
    stores only its start/end dates, not the working-day count that produced them (a
    phase's own span can cross a weekend without that weekend counting as work)."""
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def _working_days_between(earlier: date, later: date) -> int:
    """Working days strictly after `earlier` up to and including `later`."""
    count = 0
    current = earlier
    while current < later:
        current += timedelta(days=1)
        if current.weekday() < 5:
            count += 1
    return count


@dataclass(frozen=True)
class ScheduledPhase:
    sequence: int
    name: str
    kind: PhaseKind
    is_milestone: bool
    is_client_review: bool
    start_date: date
    end_date: date
    working_days: int


@dataclass(frozen=True)
class BackScheduleResult:
    phases: list[ScheduledPhase]
    project_start: date
    delivery_date: date
    is_feasible: bool
    shortfall_working_days: int  # 0 when feasible


def back_schedule(
    phase_templates: list[PhaseTemplate],
    delivery_date: date,
    volume_factor: float = 1.0,
    today: date | None = None,
) -> BackScheduleResult:
    """Walks the template in reverse from delivery_date. Each phase ends one working day
    before the next phase begins (PLANNING.md point 2); the last phase ends on delivery_date
    itself. Client-review-duration phases (kind=review, not a milestone) take their duration
    from CLIENT_REVIEW_DAYS rather than the template's stored default_days — PLANNING.md
    point 6: review windows are a studio-wide policy, not a per-phase one. Milestones stay
    zero-duration regardless of kind. Never compresses to make a past start date disappear —
    it reports the shortfall instead (PLANNING.md "Never silently compress")."""
    today = today or date.today()
    ordered = sorted(phase_templates, key=lambda p: p.sequence)

    scheduled: list[ScheduledPhase] = []
    next_start: date | None = None

    for template in reversed(ordered):
        end = delivery_date if next_start is None else _working_day_before(next_start)

        if template.is_milestone:
            working_days = 0
        elif template.kind == PhaseKind.review:
            working_days = CLIENT_REVIEW_DAYS
        else:
            working_days = template.default_days
            if template.scales_with_volume:
                working_days = round(working_days * volume_factor)

        start = end if working_days == 0 else _working_days_before(end, working_days - 1)

        scheduled.append(ScheduledPhase(
            sequence=template.sequence, name=template.name, kind=template.kind,
            is_milestone=template.is_milestone, is_client_review=template.is_client_review,
            start_date=start, end_date=end, working_days=working_days,
        ))
        next_start = start

    scheduled.reverse()
    project_start = scheduled[0].start_date if scheduled else delivery_date
    is_feasible = project_start >= today
    shortfall = 0 if is_feasible else _working_days_between(project_start, today)

    return BackScheduleResult(
        phases=scheduled, project_start=project_start, delivery_date=delivery_date,
        is_feasible=is_feasible, shortfall_working_days=shortfall,
    )


def generate_schedule(db: Session, project: Project) -> list[ProjectPhase]:
    """docs/PLANNING.md 'Data model additions'. Runs back_schedule() against the project's
    type and deadline, and persists the result as ProjectPhase rows. Regenerating a schedule
    replaces the project's existing ProjectPhase rows rather than appending — a schedule is
    derived from the template and the deadline, not something to accumulate duplicates of."""
    if project.project_type_id is None:
        raise ValueError(f"Project {project.id} has no project_type_id — cannot generate a schedule")

    templates = (
        db.query(PhaseTemplate)
        .filter_by(project_type_id=project.project_type_id)
        .order_by(PhaseTemplate.sequence)
        .all()
    )
    result = back_schedule(templates, delivery_date=project.deadline, volume_factor=project.volume_factor)

    # ORM-level delete (not a bulk .delete()) so the session's identity map is kept in sync —
    # a bulk delete leaves the old Python objects mapped to their primary keys, and SQLite's
    # rowid reuse means the new rows can be assigned those same keys, which then raises an
    # identity-map warning when they're flushed.
    for existing in db.query(ProjectPhase).filter_by(project_id=project.id).all():
        db.delete(existing)

    # templates and result.phases are index-aligned: back_schedule() sorts by sequence
    # internally the same way `templates` is already sorted here, and never drops or
    # reorders a row.
    phases = [
        ProjectPhase(
            project_id=project.id, name=p.name, kind=p.kind,
            start_date=p.start_date, end_date=p.end_date, is_milestone=p.is_milestone,
            is_anchored=False, status=ProjectPhaseStatus.not_started, assigned_person_id=None,
            required_roles=template.required_roles,
        )
        for template, p in zip(templates, result.phases)
    ]
    db.add_all(phases)
    db.commit()
    for phase in phases:
        db.refresh(phase)
    return phases


def build_feasibility_facts(
    phases: list[ProjectPhase], deadline: date, today: date | None = None
) -> dict:
    """docs/PLANNING.md 'What the AI does here'. Every number, date, and option here is
    computed before assess_schedule_feasibility's prompt is built — the model only picks
    which given candidate to call the binding constraint and writes the sentence; it never
    moves a number. Returns {"feasible": True} with nothing else when there's no shortfall
    to explain.

    Compression order (PLANNING.md "Compression order"): review windows first, then
    revision phases — never a fabrication lead time or an anchored phase. Reviews and
    revisions are the only two priorities computable today; "overlap phases that don't
    strictly depend on each other" needs a dependency graph this data model doesn't have,
    so it's not attempted rather than faked."""
    today = today or date.today()
    if not phases:
        return {"feasible": True}

    project_start = min(p.start_date for p in phases)
    if project_start >= today:
        return {"feasible": True}

    shortfall_days = _working_days_between(project_start, today)

    non_milestone = [(p, _working_days_in_range(p.start_date, p.end_date))
                     for p in phases if not p.is_milestone]
    ranked = sorted(non_milestone, key=lambda pair: -pair[1])
    binding_constraint_candidates = [
        {"phase_name": p.name, "working_days": days} for p, days in ranked[:3]
    ]

    options = []
    for p, days in non_milestone:
        if p.kind == PhaseKind.review and days > CLIENT_REVIEW_MINIMUM_DAYS:
            options.append({
                "action": "compress_review",
                "detail": f"{p.name} {days} days to {CLIENT_REVIEW_MINIMUM_DAYS}",
                "recovers_days": days - CLIENT_REVIEW_MINIMUM_DAYS,
            })
        if "revision" in p.name.lower():
            options.append({
                "action": "drop_revisions",
                "detail": f"drop {p.name} ({days} days)",
                "recovers_days": days,
            })
    options.append({
        "action": "move_delivery",
        "detail": f"to {working_days_after(deadline, shortfall_days).isoformat()}",
        "recovers_days": shortfall_days,
    })

    return {
        "feasible": False,
        "shortfall_days": shortfall_days,
        "delivery_date": deadline.isoformat(),
        "project_start": project_start.isoformat(),
        "binding_constraint_candidates": binding_constraint_candidates,
        "options": options,
    }
