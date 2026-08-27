"""docs/PLANNING.md 'Timeline view'. Pure positioning math for a hand-built bar timeline —
no Gantt library, no month-grid calendar. Percentages, not pixels, so the template stays a
plain CSS layout; the route supplies the ProjectPhase rows, this module turns their dates
into positions."""

from dataclasses import dataclass
from datetime import date, timedelta

from app.models import Project, ProjectPhase

# A 0-day milestone would otherwise render as an invisible 0%-wide bar.
MIN_BAR_WIDTH_PCT = 0.6


def week_starts(range_start: date, range_end: date) -> list[date]:
    """Mondays from the week containing range_start through the week containing range_end."""
    first_monday = range_start - timedelta(days=range_start.weekday())
    weeks = []
    current = first_monday
    while current <= range_end:
        weeks.append(current)
        current += timedelta(days=7)
    return weeks


def day_position_pct(target: date, range_start: date, total_days: int) -> float:
    return (target - range_start).days / total_days * 100


@dataclass(frozen=True)
class PhaseBar:
    phase: ProjectPhase
    left_pct: float
    width_pct: float


@dataclass(frozen=True)
class TimelineRow:
    project: Project
    bars: list[PhaseBar]


@dataclass(frozen=True)
class WeekMark:
    label_date: date
    left_pct: float


@dataclass(frozen=True)
class TimelineContext:
    rows: list[TimelineRow]
    range_start: date
    range_end: date
    week_marks: list[WeekMark]
    today_pct: float | None  # None if today falls outside the rendered range


def build_timeline(
    projects_with_phases: list[tuple[Project, list[ProjectPhase]]],
    today: date | None = None,
) -> TimelineContext:
    today = today or date.today()
    all_phases = [phase for _, phases in projects_with_phases for phase in phases]
    if not all_phases:
        return TimelineContext(rows=[], range_start=today, range_end=today, week_marks=[], today_pct=None)

    range_start = min(p.start_date for p in all_phases)
    range_end = max(p.end_date for p in all_phases)
    # Extend to full week boundaries so the header's week columns line up cleanly.
    range_start -= timedelta(days=range_start.weekday())
    range_end += timedelta(days=6 - range_end.weekday())
    total_days = (range_end - range_start).days + 1

    rows = []
    for project, phases in projects_with_phases:
        bars = []
        for phase in sorted(phases, key=lambda p: (p.start_date, p.id)):
            left = day_position_pct(phase.start_date, range_start, total_days)
            width = max(
                ((phase.end_date - phase.start_date).days + 1) / total_days * 100,
                MIN_BAR_WIDTH_PCT,
            )
            bars.append(PhaseBar(phase=phase, left_pct=left, width_pct=width))
        rows.append(TimelineRow(project=project, bars=bars))

    today_pct = (
        day_position_pct(today, range_start, total_days)
        if range_start <= today <= range_end else None
    )
    week_marks = [
        WeekMark(label_date=d, left_pct=day_position_pct(d, range_start, total_days))
        for d in week_starts(range_start, range_end)
    ]

    return TimelineContext(
        rows=rows, range_start=range_start, range_end=range_end,
        week_marks=week_marks, today_pct=today_pct,
    )


@dataclass(frozen=True)
class MilestoneEntry:
    project: Project
    phase: ProjectPhase
    is_past: bool


def milestone_list(
    projects_with_phases: list[tuple[Project, list[ProjectPhase]]],
    today: date | None = None,
) -> list[MilestoneEntry]:
    """docs/PLANNING.md 'Timeline view': "Milestone meetings surface as a list beside the
    timeline: what meeting, which project, which date, derived from the schedule." Reuses
    whatever project set and filters the caller already applied to the timeline itself —
    this is the same milestones, listed rather than plotted. Past milestones stay in the
    list rather than being dropped (a milestone that should already have happened is real
    information, not noise), flagged via is_past for the template to mute."""
    today = today or date.today()
    entries = [
        MilestoneEntry(project=project, phase=phase, is_past=phase.start_date < today)
        for project, phases in projects_with_phases
        for phase in phases
        if phase.is_milestone
    ]
    return sorted(entries, key=lambda e: (e.phase.start_date, e.project.name, e.phase.name))
