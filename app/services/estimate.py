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

# REVIEW_03.md R4: the estimator priced every shoot as internal labour days —
# phases x roles x rates — with no concept of production spend (talent, crew,
# location) at all, so a multi-brand film shoot returned a few tens of
# thousands of euros regardless of scale. These four bands, five territory
# factors and one marginal-per-brand figure are the studio's own planning
# assumptions (docs/ASSUMPTIONS.md's honesty rule applies here exactly as
# everywhere else) — not a claim to know what a real production costs.
PRODUCTION_SCALE_TIER_ORDER = ["tabletop", "single_location", "multi_location", "large_international"]
PRODUCTION_SCALE_LABELS = {
    "tabletop": "Tabletop / studio product",
    "single_location": "Single location, lifestyle",
    "multi_location": "Multi-location or talent-led",
    "large_international": "Large-scale international",
}
TERRITORY_ORDER = ["us", "uk_nordics_ch", "western_europe", "southern_europe", "central_eastern_europe"]
TERRITORY_LABELS = {
    "us": "US",
    "uk_nordics_ch": "UK / Nordics / CH",
    "western_europe": "Western Europe",
    "southern_europe": "Southern Europe",
    "central_eastern_europe": "Central / Eastern Europe",
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


@dataclass(frozen=True)
class ProductionCost:
    scale_tier: str
    territory: str
    brand_count: int
    territory_factor: float
    # Territory-adjusted, brand_count == 1 baseline — shared setup, crew and
    # location, paid once regardless of how many brands the shoot covers.
    base_spend_low: float
    base_spend_high: float
    # Territory-adjusted total for brands beyond the first — a flat per-brand
    # figure (docs/DECISIONS.md: departure from a flat multiplier on the whole
    # total, because the marginal cost of one more brand's talent buyout
    # doesn't scale with how expensive the shared set happens to be).
    brand_premium_low: float
    brand_premium_high: float
    external_spend_low: float
    external_spend_high: float


def compute_production_cost(db: Session, scale_tier: str, territory: str, brand_count: int) -> ProductionCost:
    if scale_tier not in PRODUCTION_SCALE_TIER_ORDER:
        raise ValueError(f"Unknown production scale tier {scale_tier!r}")
    if territory not in TERRITORY_ORDER:
        raise ValueError(f"Unknown territory {territory!r}")
    if brand_count < 1:
        raise ValueError(f"brand_count must be at least 1, got {brand_count}")

    raw_base_low = get_value(db, f"production_scale_{scale_tier}_low")
    raw_base_high = get_value(db, f"production_scale_{scale_tier}_high")
    raw_marginal_low = get_value(db, "multi_brand_marginal_cost_low")
    raw_marginal_high = get_value(db, "multi_brand_marginal_cost_high")
    factor = get_value(db, f"territory_factor_{territory}")

    base_spend_low = round(raw_base_low * factor)
    base_spend_high = round(raw_base_high * factor)
    brand_premium_low = round(raw_marginal_low * (brand_count - 1) * factor)
    brand_premium_high = round(raw_marginal_high * (brand_count - 1) * factor)

    return ProductionCost(
        scale_tier=scale_tier,
        territory=territory,
        brand_count=brand_count,
        territory_factor=factor,
        base_spend_low=base_spend_low,
        base_spend_high=base_spend_high,
        brand_premium_low=brand_premium_low,
        brand_premium_high=brand_premium_high,
        external_spend_low=base_spend_low + brand_premium_low,
        external_spend_high=base_spend_high + brand_premium_high,
    )


def dominant_cost_component(internal_effort_high: float, production: ProductionCost | None) -> str | None:
    """REVIEW_03.md R4.3: 'name the dominant variable.' Deterministic — the three
    components are already computed numbers, so naming the largest is a comparison,
    not narration; no AI mock involved. None when there's no shoot to compare against."""
    if production is None:
        return None
    candidates = [
        ("Internal team effort", internal_effort_high),
        ("The base production cost", production.base_spend_high),
    ]
    if production.brand_count > 1:
        candidates.append((f"Talent buyout across {production.brand_count} brands",
                           production.brand_premium_high))
    winner_label, _ = max(candidates, key=lambda pair: pair[1])
    return f"{winner_label} is the largest single swing in this figure."
