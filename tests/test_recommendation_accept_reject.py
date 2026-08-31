import json
from datetime import date, timedelta

from app.models import (
    Assignment,
    PhaseKind,
    Person,
    PersonRole,
    Priority,
    Project,
    ProjectPhase,
    ProjectPhaseStatus,
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


def _make_recommendation(db_session, project, alex, maya, assignment_id=None,
                         status=RecommendationStatus.pending):
    payload = {
        "action": "reassign", "project_id": project.id,
        "from_person_id": alex.id, "to_person_id": maya.id,
        "rationale": "test rationale",
        "impact": {"from_person_new_allocation": 0, "to_person_new_allocation": 55, "deadline_protected": True},
        "confidence": "high", "caveats": [],
    }
    facts = {"assignment_id": assignment_id} if assignment_id is not None else {}
    rec = Recommendation(
        kind=RecommendationKind.resource_reallocation, project_id=project.id,
        payload_json=json.dumps(payload), rationale="test rationale",
        computed_facts_json=json.dumps(facts), status=status,
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


def test_accept_moves_exactly_the_captured_assignment_not_whichever_matches_first(client, db_session):
    """REVIEW_02.md P3: a person can hold more than one Assignment on the same
    project (e.g. a whole-project one plus a phase-derived one) — the recommendation
    must move the specific row it was generated against, identified by
    computed_facts_json's assignment_id, not an ambiguous (project_id, person_id)
    lookup that could pick either one."""
    alex, maya, project, assignment = _seed_conflict(db_session)
    # A second assignment for the same (project, person) pair — the ambiguous case.
    other_assignment = Assignment(project_id=project.id, person_id=alex.id, allocation_pct=20,
                                  start_date=TODAY, end_date=TODAY + timedelta(days=3))
    db_session.add(other_assignment)
    db_session.commit()

    rec = _make_recommendation(db_session, project, alex, maya, assignment_id=assignment.id)
    resp = client.post(f"/recommendations/{rec.id}/accept")
    assert resp.status_code == 200

    db_session.refresh(assignment)
    db_session.refresh(other_assignment)
    assert assignment.person_id == maya.id       # the captured row moved
    assert other_assignment.person_id == alex.id  # the other one is untouched


def test_accept_syncs_the_phase_this_assignment_came_from(client, db_session):
    """REVIEW_02.md P3: accepting a resource recommendation must also update
    Timeline, not just the Assignment row. A phase-derived assignment carries a
    denormalized ProjectPhase.assigned_person_id (set by assign_phase() for
    /timeline's own display) — reassigning the Assignment without also updating
    this leaves Timeline showing the person the work was just moved away from."""
    alex, maya, project, assignment = _seed_conflict(db_session)
    phase = ProjectPhase(project_id=project.id, name="Shoot", kind=PhaseKind.production,
                         start_date=TODAY, end_date=TODAY + timedelta(days=3),
                         is_milestone=False, is_anchored=False,
                         status=ProjectPhaseStatus.not_started, assigned_person_id=alex.id,
                         required_roles="senior_designer")
    db_session.add(phase)
    db_session.flush()
    assignment.project_phase_id = phase.id
    db_session.commit()

    rec = _make_recommendation(db_session, project, alex, maya, assignment_id=assignment.id)
    resp = client.post(f"/recommendations/{rec.id}/accept")
    assert resp.status_code == 200

    db_session.refresh(assignment)
    db_session.refresh(phase)
    assert assignment.person_id == maya.id
    assert phase.assigned_person_id == maya.id
