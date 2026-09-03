from datetime import date, timedelta

from app.models import Localisation, LocalisationStatus, SubStatus
from app.services.localisation_risk import RISK_WINDOW_DAYS, check_localisation_row, summarize_by_market

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


def test_at_risk_market_card_carries_no_translator_roster(db_session):
    """REVIEW_03.md R7 (a): the original bug — a card reading 'no assigned
    translator with 4 days to deadline' next to 'assigned to Jonas and
    Camille' — came from headline describing one row and translator_ids
    aggregating every row in the market. An at-risk card must not name
    translators from other rows; it names the row it's actually about
    instead, via flagged_localisation_id."""
    flagged = make_row(project_id=1, target_market="FR", translator_id=None,
                       due_date=TODAY + timedelta(days=3))
    covered = make_row(project_id=2, target_market="FR", translator_id=7,
                       status=LocalisationStatus.in_translation,
                       due_date=TODAY + timedelta(days=20))
    db_session.add_all([flagged, covered])
    db_session.commit()

    summaries = summarize_by_market(db_session, on_date=TODAY)
    fr = next(s for s in summaries if s.market == "FR")

    assert fr.at_risk is True
    assert "no assigned translator" in fr.headline.lower()
    assert fr.translator_ids == []
    assert fr.flagged_localisation_id == flagged.id


def test_moving_queue_card_names_translators_covering_the_same_rows(db_session):
    """The not-at-risk case has no contradiction to create, so it's fine to
    name who's covering the in-flight work — as long as it's the same rows
    the headline's count is about."""
    row_a = make_row(project_id=1, target_market="DE", translator_id=3,
                     status=LocalisationStatus.in_translation,
                     due_date=TODAY + timedelta(days=20))
    row_b = make_row(project_id=2, target_market="DE", translator_id=9,
                     status=LocalisationStatus.in_translation,
                     due_date=TODAY + timedelta(days=25))
    db_session.add_all([row_a, row_b])
    db_session.commit()

    summaries = summarize_by_market(db_session, on_date=TODAY)
    de = next(s for s in summaries if s.market == "DE")

    assert de.at_risk is False
    assert "queue moving" in de.headline
    assert de.volume_in_flight == 2
    assert sorted(de.translator_ids) == [3, 9]
    assert de.flagged_localisation_id is None
