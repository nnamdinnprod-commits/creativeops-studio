import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TimestampMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ProjectStatus(str, enum.Enum):
    brief = "brief"
    ready = "ready"
    assigned = "assigned"
    in_production = "in_production"
    creative_review = "creative_review"
    approved = "approved"
    delivered = "delivered"


class ProductionTempo(str, enum.Enum):
    """REVIEW_02.md P5.3: what the readiness gate applies to. `fast_track` skips it
    entirely (a market re-version, copy swap, resize, or artwork resend). `standard`
    and `full_production` both get the existing gate — the review only describes
    fast_track as behaving differently, so both non-fast-track tiers use the one
    check that already existed rather than inventing an unspecified second one."""

    fast_track = "fast_track"
    standard = "standard"
    full_production = "full_production"


class RiskLevel(str, enum.Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"


class PersonRole(str, enum.Enum):
    producer = "producer"
    designer = "designer"
    senior_designer = "senior_designer"
    motion_designer = "motion_designer"
    copywriter = "copywriter"
    translator = "translator"


class DeliverableType(str, enum.Enum):
    social_static = "social_static"
    social_video = "social_video"
    paid_display = "paid_display"
    homepage_banner = "homepage_banner"
    email = "email"
    motion = "motion"


class DeliverableStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    in_review = "in_review"
    approved = "approved"
    delivered = "delivered"


class LocalisationStatus(str, enum.Enum):
    not_started = "not_started"
    in_translation = "in_translation"
    in_review = "in_review"
    qa = "qa"
    approved = "approved"


class SubStatus(str, enum.Enum):
    """Shared by Localisation.review_status and Localisation.qa_status."""

    pending = "pending"
    in_progress = "in_progress"
    passed = "passed"
    failed = "failed"


class VariantTheme(str, enum.Enum):
    lifestyle = "lifestyle"
    product_only = "product_only"
    ugc = "ugc"
    promotional = "promotional"


class RecommendationKind(str, enum.Enum):
    resource_reallocation = "resource_reallocation"
    production_action = "production_action"
    risk_intervention = "risk_intervention"
    localisation_action = "localisation_action"


class RecommendationStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class PhaseKind(str, enum.Enum):
    prep = "prep"
    production = "production"
    review = "review"
    delivery = "delivery"


class ProjectPhaseStatus(str, enum.Enum):
    """PLANNING.md's data model doesn't enumerate status values for ProjectPhase — inferred
    to match the not_started/in_progress/... shape used by Deliverable and Localisation
    elsewhere in this app. Logged as an assumption in DECISIONS.md."""

    not_started = "not_started"
    in_progress = "in_progress"
    complete = "complete"


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String, nullable=False)
    brand: Mapped[str] = mapped_column(String, nullable=False)
    campaign: Mapped[str] = mapped_column(String, nullable=False)
    source_market: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[Priority] = mapped_column(Enum(Priority), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), nullable=False)
    deadline: Mapped[date] = mapped_column(Date, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)
    brief_raw: Mapped[str] = mapped_column(Text, nullable=False)
    brief_analysis_id: Mapped[int | None] = mapped_column(ForeignKey("brief_analyses.id"), nullable=True)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), nullable=False, default=RiskLevel.none)
    risk_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    localisation_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estimated_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    # docs/PLANNING.md (Session 2, not yet wired to the Brief Assistant's create-project
    # flow) — nullable because every project seeded or created before this column existed
    # has neither a type nor a reason to have generated a schedule.
    project_type_id: Mapped[int | None] = mapped_column(ForeignKey("project_types.id"), nullable=True)
    volume_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # REVIEW_02.md P5.3: scopes the readiness gate (see check_readiness_gate() in
    # app/routes/pipeline.py) — pipeline stage sequence itself is unrestricted (any
    # stage to any stage), free movement was never the problem this field solves.
    production_tempo: Mapped[ProductionTempo] = mapped_column(
        Enum(ProductionTempo), nullable=False, default=ProductionTempo.standard
    )


class Person(TimestampMixin, Base):
    __tablename__ = "people"

    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[PersonRole] = mapped_column(Enum(PersonRole), nullable=False)
    capacity_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    skills: Mapped[str] = mapped_column(String, nullable=False, default="")
    is_external: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Assignment(TimestampMixin, Base):
    __tablename__ = "assignments"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)
    allocation_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    role_on_project: Mapped[str | None] = mapped_column(String, nullable=True)
    # docs/PLANNING.md "Assignments derive from phases" (Session B step 5). Null for every
    # hand-seeded or AI-recommended Assignment — set only when app/services/assignment.py's
    # assign_phase() creates this row from a ProjectPhase, so a reassignment can find and
    # replace exactly the row it produced rather than guessing by person_id/project_id alone.
    project_phase_id: Mapped[int | None] = mapped_column(ForeignKey("project_phases.id"), nullable=True)


class Deliverable(TimestampMixin, Base):
    __tablename__ = "deliverables"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    type: Mapped[DeliverableType] = mapped_column(Enum(DeliverableType), nullable=False)
    market: Mapped[str] = mapped_column(String, nullable=False)
    format_spec: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[DeliverableStatus] = mapped_column(
        Enum(DeliverableStatus), nullable=False, default=DeliverableStatus.not_started
    )
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)


class Localisation(TimestampMixin, Base):
    __tablename__ = "localisations"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    target_market: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    translator_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True)
    status: Mapped[LocalisationStatus] = mapped_column(
        Enum(LocalisationStatus), nullable=False, default=LocalisationStatus.not_started
    )
    review_status: Mapped[SubStatus] = mapped_column(Enum(SubStatus), nullable=False, default=SubStatus.pending)
    qa_status: Mapped[SubStatus] = mapped_column(Enum(SubStatus), nullable=False, default=SubStatus.pending)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class CreativeInsight(TimestampMixin, Base):
    __tablename__ = "creative_insights"

    brand: Mapped[str] = mapped_column(String, nullable=False)
    market: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(String, nullable=False)
    variant_theme: Mapped[VariantTheme] = mapped_column(Enum(VariantTheme), nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, nullable=False)
    engagement_rate: Mapped[float] = mapped_column(Float, nullable=False)
    conversion_rate: Mapped[float] = mapped_column(Float, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    insight_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # REVIEW_02.md P4: the only piece of an insight's lifecycle state that isn't
    # derivable from an existing Recommendation row — "recommendation_pending" and
    # "actioned" are computed at display time from whether a pending/accepted
    # production_action Recommendation exists for this market (app/services/insight.py's
    # compute_insight_status()), consistent with "nothing derived is stored where it can
    # drift." Dismissal has no Recommendation to derive from, so it needs real storage.
    # Set identically across every row in a market's lifestyle/product_only group —
    # dismissal is a property of the opportunity (the market-level comparison), not of
    # one raw performance row.
    dismissed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendations"

    kind: Mapped[RecommendationKind] = mapped_column(Enum(RecommendationKind), nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    computed_facts_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus), nullable=False, default=RecommendationStatus.pending
    )
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class BriefAnalysis(TimestampMixin, Base):
    __tablename__ = "brief_analyses"

    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_json: Mapped[str] = mapped_column(Text, nullable=False)
    readiness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_fields_json: Mapped[str] = mapped_column(Text, nullable=False)
    blocking_reasons: Mapped[str] = mapped_column(Text, nullable=False)
    created_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)


class ProjectType(TimestampMixin, Base):
    """docs/PLANNING.md (Session 2, not yet wired to Project or the UI)."""

    __tablename__ = "project_types"

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class PhaseTemplate(TimestampMixin, Base):
    """docs/PLANNING.md (Session 2, not yet wired to Project or the UI)."""

    __tablename__ = "phase_templates"

    project_type_id: Mapped[int] = mapped_column(ForeignKey("project_types.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    default_days: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[PhaseKind] = mapped_column(Enum(PhaseKind), nullable=False)
    required_roles: Mapped[str] = mapped_column(String, nullable=False, default="")
    is_milestone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_client_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scales_with_volume: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ProjectPhase(TimestampMixin, Base):
    """docs/PLANNING.md (Session 2). A generated, dated instance of a PhaseTemplate row for
    one project — produced by app/services/scheduling.py's generate_schedule(), not hand-
    written. Rendered at /timeline (Session B step 4); assignable at /timeline (step 5)."""

    __tablename__ = "project_phases"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[PhaseKind] = mapped_column(Enum(PhaseKind), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_milestone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_anchored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[ProjectPhaseStatus] = mapped_column(
        Enum(ProjectPhaseStatus), nullable=False, default=ProjectPhaseStatus.not_started
    )
    assigned_person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True)
    # Not in PLANNING.md's ProjectPhase column list — copied from the source PhaseTemplate row
    # at generation time (generate_schedule()) so this row is self-sufficient for candidate
    # matching even if the template changes later, or (once built) a producer inserts an
    # ad-hoc phase with no source template row at all. Same comma-separated PersonRole
    # convention as PhaseTemplate.required_roles and Person.skills.
    required_roles: Mapped[str] = mapped_column(String, nullable=False, default="")


class Assumption(TimestampMixin, Base):
    """docs/ASSUMPTIONS.md (Session 3). The studio's own editable planning heuristics —
    review cycle lengths, lead times, volume scaling, confidence bands. Every value here is
    a judgement call the studio can change, never regulatory or market data (ASSUMPTIONS.md
    is explicit about that distinction). Seeded by app/seed.py's seed_assumptions()."""

    __tablename__ = "assumptions"

    category: Mapped[str] = mapped_column(String, nullable=False)
    key: Mapped[str] = mapped_column(String, nullable=False)
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    default_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affects: Mapped[str | None] = mapped_column(String, nullable=True)


class RateBand(TimestampMixin, Base):
    """docs/ASSUMPTIONS.md (Session 3). One row per PersonRole — the studio's own day-rate
    planning figures, stated as a range, never presented as market data."""

    __tablename__ = "rate_bands"

    role: Mapped[PersonRole] = mapped_column(Enum(PersonRole), nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="EUR")
