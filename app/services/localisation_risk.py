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
