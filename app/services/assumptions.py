"""docs/ASSUMPTIONS.md. Reads and writes the studio's own editable planning heuristics —
never regulatory or market data. Every value here is deterministic Python's to read; nothing
in app/services/ai/ touches this module."""

from sqlalchemy.orm import Session

from app.models import Assumption, PersonRole, RateBand


def get_value(db: Session, key: str) -> float:
    """The live value for one Assumption key. Raises if the key doesn't exist — a missing
    key is a programming error (a typo, a seed gap), not a runtime user scenario to handle
    gracefully."""
    assumption = db.query(Assumption).filter_by(key=key).first()
    if assumption is None or assumption.value_numeric is None:
        raise ValueError(f"No numeric Assumption found for key {key!r}")
    return assumption.value_numeric


def get_text_value(db: Session, key: str) -> str:
    """Same contract as get_value(), for the rare Assumption row that's a
    sentence rather than a number (REVIEW_03.md R4: the production-cost
    coverage note)."""
    assumption = db.query(Assumption).filter_by(key=key).first()
    if assumption is None or assumption.value_text is None:
        raise ValueError(f"No text Assumption found for key {key!r}")
    return assumption.value_text


def get_rate_band(db: Session, role: PersonRole) -> RateBand | None:
    return db.query(RateBand).filter_by(role=role).first()


def reset_all(db: Session) -> None:
    """ASSUMPTIONS.md 'Interface': a reset-to-defaults control, because a demo gets run
    several times and someone will have been experimenting. Only Assumption rows reset —
    RateBand has no default_value column in ASSUMPTIONS.md's own data model, so a changed
    rate stays changed until edited back."""
    for assumption in db.query(Assumption).all():
        if assumption.default_value is not None:
            assumption.value_numeric = assumption.default_value
    db.commit()
