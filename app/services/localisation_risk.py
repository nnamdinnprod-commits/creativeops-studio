"""Deterministic localisation risk rule. Python decides `at_risk`;
app/services/ai/localisation.py only phrases the reason. See AI_WORKFLOWS.md
function 5 and PRODUCT_SPEC.md's localisation risk rule.

Pulled forward from Phase 5 because the Phase 4 dashboard attention panel needs
a localisation-risk signal to narrate — this is the same function Phase 5 will
use to surface risk on pipeline cards, not a duplicate implementation.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models import Localisation, LocalisationStatus, SubStatus

RISK_WINDOW_DAYS = 4


@dataclass
class LocalisationRiskFlag:
    localisation: Localisation
    days_to_due: int
    reason: str


def check_localisation_row(row: Localisation, on_date: date | None = None) -> LocalisationRiskFlag | None:
    on_date = on_date or date.today()
    if row.status == LocalisationStatus.approved or row.due_date is None:
        return None

    days_to_due = (row.due_date - on_date).days
    if days_to_due > RISK_WINDOW_DAYS:
        return None

    if row.translator_id is None:
        return LocalisationRiskFlag(
            localisation=row, days_to_due=days_to_due,
            reason=f"{row.target_market} review has no assigned translator with {days_to_due} days to deadline.",
        )
    if row.status == LocalisationStatus.in_review and row.review_status == SubStatus.pending:
        return LocalisationRiskFlag(
            localisation=row, days_to_due=days_to_due,
            reason=f"{row.target_market} localisation is stalled in review with {days_to_due} days to deadline.",
        )
    return None


def get_localisation_risks(db: Session, on_date: date | None = None) -> list[LocalisationRiskFlag]:
    rows = db.query(Localisation).all()
    flags = [check_localisation_row(row, on_date) for row in rows]
    return [f for f in flags if f is not None]


@dataclass
class MarketSummary:
    market: str
    volume_in_flight: int
    translator_ids: list[int]
    oldest_item: Localisation | None
    at_risk: bool
    headline: str


def summarize_by_market(db: Session, on_date: date | None = None) -> list[MarketSummary]:
    """Per-market localisation summary — volume in flight, who's assigned, the
    oldest item in the queue, and a plain-language headline naming the
    bottleneck (or confirming the queue is clear). FEEDBACK_LOG.md A2: this is
    what replaces the dashboard's bare row-count tile."""
    on_date = on_date or date.today()
    rows = db.query(Localisation).all()
    markets = sorted({r.target_market for r in rows})

    summaries = []
    for market in markets:
        market_rows = [r for r in rows if r.target_market == market]
        in_flight = [r for r in market_rows if r.status != LocalisationStatus.approved]
        flags = [f for f in (check_localisation_row(r, on_date) for r in market_rows) if f is not None]
        oldest = min(in_flight, key=lambda r: r.created_at) if in_flight else None
        translator_ids = sorted({r.translator_id for r in market_rows if r.translator_id is not None})

        if flags:
            worst = min(flags, key=lambda f: f.days_to_due)
            headline = worst.reason.rstrip(".")
        elif in_flight:
            headline = f"{market} queue moving — {len(in_flight)} in flight"
        else:
            headline = f"{market} queue clear"

        summaries.append(MarketSummary(
            market=market,
            volume_in_flight=len(in_flight),
            translator_ids=translator_ids,
            oldest_item=oldest,
            at_risk=bool(flags),
            headline=headline,
        ))

    return sorted(summaries, key=lambda s: (not s.at_risk, -s.volume_in_flight))
