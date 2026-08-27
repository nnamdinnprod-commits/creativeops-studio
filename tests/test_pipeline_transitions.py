from datetime import date, timedelta

from app.config import settings
from app.models import BriefAnalysis, Person, PersonRole, Priority, Project, ProjectStatus

TODAY = date(2026, 8, 21)


def _seed_project(db_session, status=ProjectStatus.brief, brief_analysis_id=None):
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100,
                   skills="", is_external=False)
    db_session.add(owner)
    db_session.flush()

    project = Project(name="P1", brand="Albelli", campaign="C", source_market="NL",
                      priority=Priority.medium, status=status,
                      deadline=TODAY + timedelta(days=30), owner_id=owner.id,
                      brief_raw="x", brief_analysis_id=brief_analysis_id)
    db_session.add(project)
    db_session.commit()
    return project


def _seed_analysis(db_session, readiness_score):
    analysis = BriefAnalysis(raw_text="x", extracted_json="{}", readiness_score=readiness_score,
                             missing_fields_json="[]", blocking_reasons="")
    db_session.add(analysis)
    db_session.commit()
    return analysis


def test_skipping_a_stage_forward_is_refused_with_a_reason(client, db_session):
    project = _seed_project(db_session, status=ProjectStatus.brief)

    resp = client.post(f"/pipeline/{project.id}/status", data={"status": ProjectStatus.assigned.value})
    assert resp.status_code == 200
    assert "must pass through" in resp.text

    db_session.refresh(project)
    assert project.status == ProjectStatus.brief  # unchanged


def test_moving_forward_one_stage_is_allowed(client, db_session):
    project = _seed_project(db_session, status=ProjectStatus.brief)

    resp = client.post(f"/pipeline/{project.id}/status", data={"status": ProjectStatus.ready.value})
    assert resp.status_code == 200

    db_session.refresh(project)
    assert project.status == ProjectStatus.ready


def test_moving_backward_is_allowed_freely(client, db_session):
    project = _seed_project(db_session, status=ProjectStatus.in_production)

    resp = client.post(f"/pipeline/{project.id}/status", data={"status": ProjectStatus.brief.value})
    assert resp.status_code == 200

    db_session.refresh(project)
    assert project.status == ProjectStatus.brief


def test_low_readiness_score_blocks_moving_past_ready(client, db_session):
    analysis = _seed_analysis(db_session, readiness_score=settings.brief_readiness_threshold - 1)
    project = _seed_project(db_session, status=ProjectStatus.ready, brief_analysis_id=analysis.id)

    resp = client.post(f"/pipeline/{project.id}/status", data={"status": ProjectStatus.assigned.value})
    assert resp.status_code == 200
    assert "readiness" in resp.text.lower()
    assert str(analysis.readiness_score) in resp.text

    db_session.refresh(project)
    assert project.status == ProjectStatus.ready  # unchanged


def test_readiness_score_at_or_above_threshold_allows_the_move(client, db_session):
    analysis = _seed_analysis(db_session, readiness_score=settings.brief_readiness_threshold)
    project = _seed_project(db_session, status=ProjectStatus.ready, brief_analysis_id=analysis.id)

    resp = client.post(f"/pipeline/{project.id}/status", data={"status": ProjectStatus.assigned.value})
    assert resp.status_code == 200

    db_session.refresh(project)
    assert project.status == ProjectStatus.assigned


def test_project_with_no_brief_analysis_is_not_gated(client, db_session):
    project = _seed_project(db_session, status=ProjectStatus.ready, brief_analysis_id=None)

    resp = client.post(f"/pipeline/{project.id}/status", data={"status": ProjectStatus.assigned.value})
    assert resp.status_code == 200

    db_session.refresh(project)
    assert project.status == ProjectStatus.assigned
