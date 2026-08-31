import json
from datetime import date, timedelta

from app.config import settings
from app.models import BriefAnalysis, Person, PersonRole, Priority, ProductionTempo, Project, ProjectStatus

TODAY = date(2026, 8, 21)


def _seed_project(db_session, status=ProjectStatus.brief, brief_analysis_id=None,
                  production_tempo=ProductionTempo.standard):
    owner = Person(name="Owner", role=PersonRole.producer, capacity_pct=100,
                   skills="", is_external=False)
    db_session.add(owner)
    db_session.flush()

    project = Project(name="P1", brand="Fotomera", campaign="C", source_market="NL",
                      priority=Priority.medium, status=status,
                      deadline=TODAY + timedelta(days=30), owner_id=owner.id,
                      brief_raw="x", brief_analysis_id=brief_analysis_id,
                      production_tempo=production_tempo)
    db_session.add(project)
    db_session.commit()
    return project


def _seed_analysis(db_session, readiness_score, missing_fields=None):
    analysis = BriefAnalysis(raw_text="x", extracted_json="{}", readiness_score=readiness_score,
                             missing_fields_json=json.dumps(missing_fields or []), blocking_reasons="")
    db_session.add(analysis)
    db_session.commit()
    return analysis


def test_skipping_a_stage_forward_is_allowed(client, db_session):
    """REVIEW_02.md P5.3: sequence is free -- any stage to any stage. A market
    re-version, copy swap, resize, or artwork resend can legitimately skip ahead;
    the readiness gate (not stage sequence) is what should stop an unready project,
    and only past Ready with a brief analysis on record (see the gate tests below)."""
    project = _seed_project(db_session, status=ProjectStatus.brief)

    resp = client.post(f"/pipeline/{project.id}/status", data={"status": ProjectStatus.creative_review.value})
    assert resp.status_code == 200

    db_session.refresh(project)
    assert project.status == ProjectStatus.creative_review


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
    analysis = _seed_analysis(db_session, readiness_score=settings.brief_readiness_threshold - 1,
                              missing_fields=["format_spec", "approval_owner"])
    project = _seed_project(db_session, status=ProjectStatus.ready, brief_analysis_id=analysis.id)

    resp = client.post(f"/pipeline/{project.id}/status", data={"status": ProjectStatus.assigned.value})
    assert resp.status_code == 200
    assert "readiness" in resp.text.lower()
    assert str(analysis.readiness_score) in resp.text
    # REVIEW_02.md P5.3: "the reason naming what is missing and what it blocks."
    assert "format_spec" in resp.text
    assert "approval_owner" in resp.text

    db_session.refresh(project)
    assert project.status == ProjectStatus.ready  # unchanged


def test_fast_track_skips_the_readiness_gate(client, db_session):
    """REVIEW_02.md P5.3: fast-track items skip the gate entirely."""
    analysis = _seed_analysis(db_session, readiness_score=settings.brief_readiness_threshold - 1,
                              missing_fields=["format_spec"])
    project = _seed_project(db_session, status=ProjectStatus.ready, brief_analysis_id=analysis.id,
                            production_tempo=ProductionTempo.fast_track)

    resp = client.post(f"/pipeline/{project.id}/status", data={"status": ProjectStatus.delivered.value})
    assert resp.status_code == 200

    db_session.refresh(project)
    assert project.status == ProjectStatus.delivered


def test_full_production_is_still_gated_like_standard(client, db_session):
    analysis = _seed_analysis(db_session, readiness_score=settings.brief_readiness_threshold - 1,
                              missing_fields=["format_spec"])
    project = _seed_project(db_session, status=ProjectStatus.ready, brief_analysis_id=analysis.id,
                            production_tempo=ProductionTempo.full_production)

    resp = client.post(f"/pipeline/{project.id}/status", data={"status": ProjectStatus.assigned.value})
    assert resp.status_code == 200
    assert "format_spec" in resp.text

    db_session.refresh(project)
    assert project.status == ProjectStatus.ready  # unchanged


def test_new_project_defaults_to_standard_tempo(db_session):
    project = _seed_project(db_session)
    assert project.production_tempo == ProductionTempo.standard


def test_tempo_route_updates_the_project(client, db_session):
    project = _seed_project(db_session)

    resp = client.post(f"/pipeline/{project.id}/tempo", data={"tempo": "fast_track"})
    assert resp.status_code == 200

    db_session.refresh(project)
    assert project.production_tempo == ProductionTempo.fast_track


def test_tempo_route_rejects_an_invalid_value(client, db_session):
    project = _seed_project(db_session)

    resp = client.post(f"/pipeline/{project.id}/tempo", data={"tempo": "urgent"})
    assert resp.status_code == 200
    assert "not a valid tempo" in resp.text

    db_session.refresh(project)
    assert project.production_tempo == ProductionTempo.standard  # unchanged


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
