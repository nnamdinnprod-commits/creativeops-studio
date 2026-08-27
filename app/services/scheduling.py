"""docs/PLANNING.md 'Back-scheduling'. Deterministic — dates and day-counts are computed
here, never by the model. Session B step 2: this is a pure function over PhaseTemplate rows;
it does not read or write ProjectPhase (that table doesn't exist until step 3)."""

from dataclasses import dataclass
from datetime import date, timedelta

from app.models import PhaseKind, PhaseTemplate

# docs/ASSUMPTIONS.md "Review and approval cycles". Session C builds the editable Assumption
# table; until then this is the fixed value that table would otherwise hold.
CLIENT_REVIEW_DAYS = 3

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
