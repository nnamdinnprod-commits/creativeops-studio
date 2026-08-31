from app.models import BriefAnalysis, Deliverable, Localisation, Person, PersonRole, Project


def test_analyse_then_create_project_persists_everything(client, db_session):
    """End-to-end through the actual routes, in mock AI mode (no key needed)."""
    db_session.add(Person(name="Sam", role=PersonRole.producer, capacity_pct=100,
                          skills="", is_external=False))
    db_session.commit()

    raw_text = (
        "Mother's Day social static set, UK and ES, 6 variants, 1080x1080, "
        "approved by Sam, audience existing + prospecting customers."
    )
    analyse_resp = client.post("/brief/analyse", data={"raw_text": raw_text})
    assert analyse_resp.status_code == 200

    analysis = db_session.query(BriefAnalysis).order_by(BriefAnalysis.id.desc()).first()
    assert analysis is not None
    assert analysis.readiness_score > 0
    assert analysis.raw_text == raw_text

    create_resp = client.post("/brief/create-project", data={
        "analysis_id": analysis.id,
        "project_name": "Mothers Day Test",
        "brand": "Halveth",
    })
    assert create_resp.status_code == 200

    project = db_session.query(Project).filter_by(name="Mothers Day Test").first()
    assert project is not None
    assert project.status.value == "brief"
    assert project.brief_analysis_id == analysis.id
    assert project.brief_raw == raw_text
    assert project.localisation_required is True

    db_session.refresh(analysis)
    assert analysis.created_project_id == project.id

    deliverables = db_session.query(Deliverable).filter_by(project_id=project.id).all()
    assert len(deliverables) >= 1

    localisations = db_session.query(Localisation).filter_by(project_id=project.id).all()
    assert len(localisations) >= 1


def test_create_project_with_unknown_analysis_id_shows_fallback_not_a_traceback(client, db_session):
    resp = client.post("/brief/create-project", data={
        "analysis_id": 999999,
        "project_name": "Should Not Exist",
        "brand": "Halveth",
    })
    assert resp.status_code == 200
    assert db_session.query(Project).filter_by(name="Should Not Exist").first() is None
