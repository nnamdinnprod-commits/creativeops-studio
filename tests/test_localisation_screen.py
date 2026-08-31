from datetime import date

from app.models import Localisation, LocalisationStatus, Person, PersonRole, Priority, Project, ProjectStatus, SubStatus

TODAY = date(2026, 8, 21)


def _seed(db_session):
    owner = Person(name="Sam", role=PersonRole.producer, capacity_pct=100, skills="", is_external=False)
    jonas = Person(name="Jonas", role=PersonRole.translator, capacity_pct=100, skills="copy_de",
                   is_external=True)
    db_session.add_all([owner, jonas])
    db_session.flush()

    project = Project(name="P1", brand="Fotomera", campaign="C", source_market="NL",
                      priority=Priority.medium, status=ProjectStatus.ready,
                      deadline=TODAY, owner_id=owner.id, brief_raw="x", localisation_required=True)
    db_session.add(project)
    db_session.flush()

    loc = Localisation(project_id=project.id, target_market="DE", language="de",
                       translator_id=None, status=LocalisationStatus.not_started,
                       review_status=SubStatus.pending, qa_status=SubStatus.pending, due_date=TODAY)
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
    assert resp.headers["location"] == "/localisation?market=DE"  # not bounced to /projects/...

    db_session.refresh(loc)
    assert loc.translator_id == jonas.id


def test_assign_with_no_return_to_falls_back_to_project_page(client, db_session):
    """Backward compatible with project_detail.html's existing assign form, which
    posts no return_to field at all."""
    project, jonas, loc = _seed(db_session)

    resp = client.post(f"/localisation/{loc.id}/assign",
                       data={"translator_id": jonas.id}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/projects/{project.id}"


def test_assign_ignores_an_unsafe_return_to(client, db_session):
    """Only ever redirects back to a page this app itself serves the form from —
    never follows an arbitrary posted URL."""
    project, jonas, loc = _seed(db_session)

    resp = client.post(f"/localisation/{loc.id}/assign",
                       data={"translator_id": jonas.id, "return_to": "https://evil.example/"},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/projects/{project.id}"
