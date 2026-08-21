from datetime import date, timedelta

from app.models import Localisation, LocalisationStatus, SubStatus
from app.services.localisation_risk import RISK_WINDOW_DAYS, check_localisation_row

TODAY = date(2026, 8, 21)


def make_row(**overrides):
    defaults = dict(
        project_id=1, target_market="FR", language="fr", translator_id=None,
        status=LocalisationStatus.not_started, review_status=SubStatus.pending,
        qa_status=SubStatus.pending, due_date=TODAY + timedelta(days=3),
    )
    defaults.update(overrides)
    return Localisation(**defaults)


def test_no_translator_within_risk_window_is_at_risk():
    row = make_row(translator_id=None, due_date=TODAY + timedelta(days=3))
    flag = check_localisation_row(row, on_date=TODAY)
    assert flag is not None
    assert flag.days_to_due == 3
    assert "FR" in flag.reason
    assert "translator" in flag.reason.lower()


def test_no_translator_outside_risk_window_is_not_at_risk():
    row = make_row(translator_id=None, due_date=TODAY + timedelta(days=RISK_WINDOW_DAYS + 5))
    assert check_localisation_row(row, on_date=TODAY) is None


def test_exactly_at_the_window_boundary_is_at_risk():
    row = make_row(translator_id=None, due_date=TODAY + timedelta(days=RISK_WINDOW_DAYS))
    assert check_localisation_row(row, on_date=TODAY) is not None


def test_translator_assigned_and_progressing_is_not_at_risk():
    row = make_row(translator_id=5, status=LocalisationStatus.in_translation,
                   due_date=TODAY + timedelta(days=2))
    assert check_localisation_row(row, on_date=TODAY) is None


def test_stalled_in_review_with_translator_is_at_risk():
    row = make_row(translator_id=5, status=LocalisationStatus.in_review,
                   review_status=SubStatus.pending, due_date=TODAY + timedelta(days=2))
    flag = check_localisation_row(row, on_date=TODAY)
    assert flag is not None
    assert "stalled" in flag.reason.lower()


def test_approved_is_never_at_risk_even_if_overdue_and_unassigned():
    row = make_row(translator_id=None, status=LocalisationStatus.approved,
                   due_date=TODAY - timedelta(days=5))
    assert check_localisation_row(row, on_date=TODAY) is None


def test_no_due_date_is_never_at_risk():
    row = make_row(translator_id=None, due_date=None)
    assert check_localisation_row(row, on_date=TODAY) is None
