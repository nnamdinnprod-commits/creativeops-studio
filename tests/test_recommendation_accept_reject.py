import json
from datetime import date, timedelta

from app.models import (
    Assignment,
    Person,
    PersonRole,
    Priority,
    Project,
    ProjectStatus,
    Recommendation,
    RecommendationKind,
    RecommendationStatus,
)

TODAY = date(2026, 8, 21)


def _seed_conflict(db_session):
    alex = Person(name="Alex", role=PersonRole.senior_designer, capacity_pct=80,
                 skills="layout", is_external=False)
    maya = Person(name="Maya", role=PersonRole.designer, capacity_pct=100,
                 skills="layout", is_external=False)
    db_session.add_all([alex, maya])
    db_session.flush()

    project = Project(name="P1", brand="Fotomera", campaign="C", source_market="NL",
                      priority=Priority.high, status=ProjectStatus.in_production,
                      deadline=TODAY + timedelta(days=5), owner_id=alex.id, brief_raw="x")
    db_session.add(project)
    db_session.flush()

    assignment = Assignment(project_id=project.id, person_id=alex.id, allocation_pct=55,
                            start_date=TODAY - timedelta(days=2), end_date=TODAY + timedelta(days=5))
    db_session.add(assignment)
    db_session.commit()

    return alex, maya, project, assignment


def _make_recommendation(db_session, project, alex, maya, status=RecommendationStatus.pending):
    payload = {
        "action": "reassign", "project_id": project.id,
        "from_person_id": alex.id, "to_person_id": maya.id,
        "rationale": "test rationale",
        "impact": {"from_person_new_allocation": 0, "to_person_new_allocation": 55, "deadline_protected": True},
        "confidence": "high", "caveats": [],
    }
    rec = Recommendation(
        kind=RecommendationKind.resource_reallocation, project_id=project.id,
        payload_json=json.dumps(payload), rationale="test rationale",
        computed_facts_json="{}", status=status,
    )
    db_session.add(rec)
    db_session.commit()
    return rec


def test_reject_leaves_assignment_untouched_and_stays_in_history(client, db_session):
    alex, maya, project, assignment = _seed_conflict(db_session)
    rec = _make_recommendation(db_session, project, alex, maya)

    resp = client.post(f"/recommendations/{rec.id}/reject")
    assert resp.status_code == 200

    db_session.refresh(assignment)
    assert assignment.person_id == alex.id  # unchanged

    db_session.refresh(rec)
    assert rec.status == RecommendationStatus.rejected
    assert rec.outcome_note is not None
    assert rec.decided_at is not None


def test_accept_moves_the_assignment_and_records_outcome(client, db_session):
    alex, maya, project, assignment = _seed_conflict(db_session)
    rec = _make_recommendation(db_session, project, alex, maya)

    resp = client.post(f"/recommendations/{rec.id}/accept")
    assert resp.status_code == 200

    db_session.refresh(assignment)
    assert assignment.person_id == maya.id  # moved

    db_session.refresh(rec)
    assert rec.status == RecommendationStatus.accepted
    assert "Maya" in rec.outcome_note


def test_accepting_an_already_decided_recommendation_is_a_no_op(client, db_session):
    alex, maya, project, assignment = _seed_conflict(db_session)
    rec = _make_recommendation(db_session, project, alex, maya, status=RecommendationStatus.accepted)

    resp = client.post(f"/recommendations/{rec.id}/accept")
    assert resp.status_code == 200

    db_session.refresh(assignment)
    assert assignment.person_id == alex.id  # not re-applied
