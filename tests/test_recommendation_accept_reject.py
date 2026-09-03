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
    ProjectStatus,
    Recommendation,
    RecommendationKind,
    RecommendationStatus,
)
from app.services.assignment import assigned_person_ids_by_phase

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


def _make_recommendation(db_session, project, alex, maya, assignment, option_label="A",
                         status=RecommendationStatus.pending):
    """REVIEW_02.md P5.6: payload carries the ranked options list, matching what
    recommend_resource() actually persists — a single "A: reassign to Maya" option
    by default, since that's all these accept/reject tests exercise."""
    payload = {
        "project_id": project.id,
        "options": [{
            "label": "A", "kind": "reassign", "action": "Reassign to Maya",
            "detail": "no cost, available today",
            "to_person_id": maya.id, "new_deadline": None,
        }],
        "recommended_label": "A",
        "rationale": "test rationale", "confidence": "high", "caveats": [],
    }
    facts = {
        "assignment_id": assignment.id,
        "overloaded_person": {"id": alex.id, "name": alex.name, "capacity_pct": alex.capacity_pct,
                              "allocated_pct": 95},
    }
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
    rec = _make_recommendation(db_session, project, alex, maya, assignment)

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
    rec = _make_recommendation(db_session, project, alex, maya, assignment)

    resp = client.post(f"/recommendations/{rec.id}/accept")
    assert resp.status_code == 200

    db_session.refresh(assignment)
    assert assignment.person_id == maya.id  # moved

    db_session.refresh(rec)
    assert rec.status == RecommendationStatus.accepted
    assert "Maya" in rec.outcome_note


def test_accepting_an_already_decided_recommendation_is_a_no_op(client, db_session):
    alex, maya, project, assignment = _seed_conflict(db_session)
    rec = _make_recommendation(db_session, project, alex, maya, assignment, status=RecommendationStatus.accepted)

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

    rec = _make_recommendation(db_session, project, alex, maya, assignment)
    resp = client.post(f"/recommendations/{rec.id}/accept")
    assert resp.status_code == 200

    db_session.refresh(assignment)
    db_session.refresh(other_assignment)
    assert assignment.person_id == maya.id       # the captured row moved
    assert other_assignment.person_id == alex.id  # the other one is untouched


def test_accept_syncs_the_phase_this_assignment_came_from(client, db_session):
    """REVIEW_02.md P3 / REVIEW_03.md item 5: accepting a resource
    recommendation must also update Timeline, not just the Assignment row.
    "Who's assigned to this phase" is computed live from Assignment rows
    (assigned_person_ids_by_phase) rather than a stored, separately-synced
    ProjectPhase.assigned_person_id — reassigning the Assignment is itself
    the whole fix, since there's nothing else left to fall out of sync."""
    alex, maya, project, assignment = _seed_conflict(db_session)
    phase = ProjectPhase(project_id=project.id, name="Shoot", kind=PhaseKind.production,
                         start_date=TODAY, end_date=TODAY + timedelta(days=3),
                         is_milestone=False, is_anchored=False,
                         required_roles="senior_designer")
    db_session.add(phase)
    db_session.flush()
    assignment.project_phase_id = phase.id
    db_session.commit()

    rec = _make_recommendation(db_session, project, alex, maya, assignment)
    resp = client.post(f"/recommendations/{rec.id}/accept")
    assert resp.status_code == 200

    db_session.refresh(assignment)
    assert assignment.person_id == maya.id
    assert assigned_person_ids_by_phase(db_session, [phase.id]) == {phase.id: maya.id}
