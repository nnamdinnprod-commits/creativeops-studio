from datetime import date, timedelta

from app.models import Localisation, LocalisationStatus, Person, PersonRole, Priority, Project, ProjectStatus, SubStatus
from app.seed import seed_assumptions

TODAY = date.today()  # app/routes/pipeline.py's assign_translator uses date.today() internally


def _seed(db_session, due_date=None):
    seed_assumptions(db_session)
    owner = Person(name="Sam", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    jonas = Person(name="Jonas", role=PersonRole.translator, capacity_pct=100, skills="copy_de",
                   is_external=True)
    db_session.add_all([owner, jonas])
    db_session.flush()

    project = Project(name="P1", brand="Fotomera", campaign="C", source_market="NL",
                      priority=Priority.medium, status=ProjectStatus.ready,
                      deadline=TODAY + timedelta(days=30), owner_id=owner.id, brief_raw="x",
                      localisation_required=True)
    db_session.add(project)
    db_session.flush()

    # Due date left far enough out that Jonas's seeded 3-day translator lead time
    # (app/seed.py RATE_BANDS) doesn't itself block the assign in tests that don't
    # care about lead time -- see test_engagement_lead_time.py for that behaviour.
    loc = Localisation(project_id=project.id, target_market="DE", language="de",
                       translator_id=None, status=LocalisationStatus.not_started,
                       review_status=SubStatus.pending, qa_status=SubStatus.pending,
                       due_date=due_date or TODAY + timedelta(days=10))
    db_session.add(loc)
    db_session.commit()
    return project, jonas, loc


def test_unassigned_row_shows_an_inline_assign_form(client, db_session):
    """REVIEW_02.md P3: '/localisation' used to be read-only — no way to assign a
    translator without navigating away to the project page. The grid must offer
    the same assign action the project page already had."""
    project, jonas, loc = _seed(db_session)

    resp = client.get("/localisation")
    assert resp.status_code == 200
    assert f'action="/localisation/{loc.id}/assign"' in resp.text
    assert "Jonas" in resp.text


def test_assign_from_localisation_page_persists_and_stays_on_the_page(client, db_session):
    project, jonas, loc = _seed(db_session)

    resp = client.post(f"/localisation/{loc.id}/assign",
                       data={"translator_id": jonas.id, "return_to": "/localisation?market=DE"},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/localisation?market=DE&assign_success=")  # not bounced to /projects/...

    db_session.refresh(loc)
    assert loc.translator_id == jonas.id


def test_assign_with_no_return_to_falls_back_to_project_page(client, db_session):
    """Backward compatible with project_detail.html's existing assign form, which
    posts no return_to field at all."""
    project, jonas, loc = _seed(db_session)

    resp = client.post(f"/localisation/{loc.id}/assign",
                       data={"translator_id": jonas.id}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith(f"/projects/{project.id}?assign_success=")


def test_market_card_links_to_filter_the_grid_below(client, db_session):
    """REVIEW_03.md R7 (b): the four market cards used to do nothing — only
    the grid's own project links worked. Each card must filter the grid to
    its market."""
    _seed(db_session)
    resp = client.get("/localisation")
    assert resp.status_code == 200
    assert 'href="/localisation?market=DE"' in resp.text


def test_at_risk_market_card_carries_its_own_assign_control(client, db_session):
    """REVIEW_03.md R7 (c): a card reporting a problem must offer a way to
    act on it, not just describe it."""
    project, jonas, loc = _seed(db_session, due_date=TODAY + timedelta(days=3))
    resp = client.get("/localisation")
    assert resp.status_code == 200
    assert "no assigned translator" in resp.text.lower()
    assert f'action="/localisation/{loc.id}/assign"' in resp.text
    # The at-risk card names no one — that was the original self-contradiction.
    assert "Handled by" not in resp.text


def test_assigning_from_the_market_card_clears_its_own_risk_headline(client, db_session):
    project, jonas, loc = _seed(db_session, due_date=TODAY + timedelta(days=3))
    before = client.get("/localisation")
    assert "no assigned translator" in before.text.lower()

    client.post(f"/localisation/{loc.id}/assign", data={"translator_id": jonas.id})

    after = client.get("/localisation")
    assert "no assigned translator" not in after.text.lower()


def test_assign_ignores_an_unsafe_return_to(client, db_session):
    """Only ever redirects back to a page this app itself serves the form from —
    never follows an arbitrary posted URL."""
    project, jonas, loc = _seed(db_session)

    resp = client.post(f"/localisation/{loc.id}/assign",
                       data={"translator_id": jonas.id, "return_to": "https://evil.example/"},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith(f"/projects/{project.id}?assign_success=")
