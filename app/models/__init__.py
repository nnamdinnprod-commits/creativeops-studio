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
