"""docs/BRIEF_MODES.md 'Quick Estimate mode' and 'Costing'. Deterministic — every duration
and cost number here is computed from ASSUMPTIONS.md-backed values (read live from the
Assumption/RateBand tables, not scheduling.py's hardcoded constants — this module is the
first real consumer ASSUMPTIONS.md and DECISIONS.md 025 pointed forward to) and the matched
ProjectType's PhaseTemplate rows. app/services/ai/estimate.py's quick_estimate() only infers
the request shape; it never produces a day count or a price."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models import PersonRole, PhaseKind, PhaseTemplate, ProjectType
from app.services.assumptions import get_rate_band, get_value
from app.services.scheduling import working_days_after

WORK_TYPE_TO_PROJECT_TYPE = {
    "film": "Film / branded content",
    "event": "Event",
    "stills": "Stills",
    "social": "Social / AI-generated content",
}

CONFIDENCE_FACTOR_KEYS: dict[str, tuple[str, str]] = {
    "high": ("confidence_high_low_factor", "confidence_high_high_factor"),
    "medium": ("confidence_medium_low_factor", "confidence_medium_high_factor"),
    "low_medium": ("confidence_low_medium_low_factor", "confidence_low_medium_high_factor"),
    "low": ("confidence_low_low_factor", "confidence_low_high_factor"),
}


def volume_factor_for(db: Session, asset_count: int) -> float:
    """The live ASSUMPTIONS.md 'Volume scaling' bands — deliberately a separate read from
    app/services/scheduling.py's volume_factor_for(), which stays on its own hardcoded
    constant (DECISIONS.md 025/018/019). This one is what "editable, recomputes live"
    actually means."""
    bands = [
        (1, 6, get_value(db, "volume_scale_1_6")),
        (7, 15, get_value(db, "volume_scale_7_15")),
        (16, 30, get_value(db, "volume_scale_16_30")),
        (31, 60, get_value(db, "volume_scale_31_60")),
    ]
    for low, high, factor in bands:
        if low <= asset_count <= high:
            return factor
    raise ValueError(f"asset_count {asset_count} is outside the supported 1-60 range")


@dataclass(frozen=True)
class CostLine:
    role: PersonRole
    days: float
    low_rate: float
    high_rate: float


@dataclass(frozen=True)
class ComputedEstimate:
    duration_low_days: float
    duration_high_days: float
    cost_low: float
    cost_high: float
    currency: str
    earliest_delivery: date
    lines: list[CostLine]


def compute_estimate(
    db: Session,
    work_type: str,
    asset_count: int,
    original_photography: bool,
    review_rounds: int,
    target_market_count: int,
    localisation_required: bool,
    confidence: str,
    today: date | None = None,
) -> ComputedEstimate:
    today = today or date.today()
    project_type_name = WORK_TYPE_TO_PROJECT_TYPE.get(work_type)
    if project_type_name is None:
        raise ValueError(f"Unknown work_type {work_type!r}")
    if confidence not in CONFIDENCE_FACTOR_KEYS:
        raise ValueError(f"Unknown confidence band {confidence!r}")

    project_type = db.query(ProjectType).filter_by(name=project_type_name).one()
    templates = (
        db.query(PhaseTemplate)
        .filter_by(project_type_id=project_type.id)
        .order_by(PhaseTemplate.sequence)
        .all()
    )
    factor = volume_factor_for(db, asset_count)

    lines: list[CostLine] = []
    total_days = 0.0

    def add_line(role: PersonRole, days: float) -> None:
        nonlocal total_days
        total_days += days
        band = get_rate_band(db, role)
        if band is not None:
            lines.append(CostLine(role=role, days=days, low_rate=band.low, high_rate=band.high))

    # The template's own prep/production/delivery phases. Review-kind, non-milestone phases
    # are excluded here — review time is the review_rounds control below, not whatever days
    # a specific template row happens to store (the same rule back_schedule() already
    # applies for generated schedules, PLANNING.md point 6).
    #
    # Volume scaling applies to every production-kind phase here, not just rows flagged
    # scales_with_volume — that flag is Session B's, tuned for precise generated schedules,
    # and today only Film's Shoot/Delivery rows carry it (DECISIONS.md 016). A quick
    # estimate is coarser by nature: more assets should mean more production time for any
    # work type, including the doc's own primary example (social), not only the one type
    # that happens to have the flag set. This is a deliberate divergence from
    # back_schedule()'s per-phase flag, not an oversight — see DECISIONS.md 026.
    for template in templates:
        if template.is_milestone or template.kind == PhaseKind.review:
            continue
        days = template.default_days * factor if template.kind == PhaseKind.production else template.default_days
        for role_name in (r.strip() for r in template.required_roles.split(",") if r.strip()):
            add_line(PersonRole(role_name), days)

    client_review_days = get_value(db, "client_review_days")
    add_line(PersonRole.producer, review_rounds * client_review_days)

    if original_photography:
        add_line(PersonRole.senior_designer, get_value(db, "talent_booking_lead_days"))

    if localisation_required and target_market_count > 0:
        loc_days = get_value(db, "localisation_review_days") * target_market_count
        add_line(PersonRole.translator, loc_days)

    low_key, high_key = CONFIDENCE_FACTOR_KEYS[confidence]
    low_factor = get_value(db, low_key)
    high_factor = get_value(db, high_key)

    duration_low = total_days * low_factor
    duration_high = total_days * high_factor

    cost_low_raw = sum(line.days * line.low_rate for line in lines)
    cost_high_raw = sum(line.days * line.high_rate for line in lines)

    earliest_delivery = working_days_after(today, round(duration_high))

    return ComputedEstimate(
        duration_low_days=round(duration_low, 1),
        duration_high_days=round(duration_high, 1),
        cost_low=round(cost_low_raw * low_factor),
        cost_high=round(cost_high_raw * high_factor),
        currency="EUR",
        earliest_delivery=earliest_delivery,
        lines=lines,
    )
