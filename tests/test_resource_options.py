"""REVIEW_02.md P5.6: "a real decision has alternatives with different costs" --
recommend_resource returns a ranked set of options (reassign / engage external /
move delivery), not a single take-it-or-leave-it action. These exercise the real
pipeline end to end (_build_conflict_facts -> recommend_resource -> accept), not
hand-built payloads -- that's what caught two real bugs during manual testing that
no hand-built-payload test would ever have found."""

import json
from datetime import date, timedelta

from app.models import (
    Assignment,
    Person,
    PersonRole,
    Priority,
    Project,
    ProjectStatus,
    RateBand,
    Recommendation,
    RecommendationKind,
)
from app.routes.resources import _build_conflict_facts
from app.seed import seed_assumptions
from app.services.capacity import all_person_capacities, get_conflicts

TODAY = date.today()  # resources.py's routes use date.today() internally


def _seed_conflict(db_session, project_deadline_days=14, add_external_candidate=True):
    seed_assumptions(db_session)
    alex = Person(name="Alex", role=PersonRole.senior_designer, capacity_pct=80,
                 skills="layout", is_external=False)
    maya = Person(name="Maya", role=PersonRole.designer, capacity_pct=100,
                 skills="layout", is_external=False)
    db_session.add_all([alex, maya])
    people = [alex, maya]
    if add_external_candidate:
        lars = Person(name="Lars", role=PersonRole.motion_designer, capacity_pct=100,
                     skills="motion", is_external=True)
        db_session.add(lars)
        people.append(lars)
    db_session.flush()

    p1 = Project(name="Urgent Project", brand="Fotomera", campaign="C", source_market="NL",
                priority=Priority.high, status=ProjectStatus.in_production,
                deadline=TODAY + timedelta(days=2), owner_id=alex.id, brief_raw="x")
    p2 = Project(name="Overlapping Project", brand="Fotomera", campaign="C", source_market="NL",
                priority=Priority.medium, status=ProjectStatus.assigned,
                deadline=TODAY + timedelta(days=project_deadline_days), owner_id=alex.id, brief_raw="x")
    db_session.add_all([p1, p2])
    db_session.flush()

    # Window ends well before an external motion designer's 5-day seeded lead
    # time (app/seed.py RATE_BANDS) could fit -- deliberately narrower than a1's
    # deadline is high-priority-tight for.
    a1 = Assignment(project_id=p1.id, person_id=alex.id, allocation_pct=55,
                    start_date=TODAY - timedelta(days=2), end_date=TODAY + timedelta(days=2))
    a2 = Assignment(project_id=p2.id, person_id=alex.id, allocation_pct=40,
                    start_date=TODAY - timedelta(days=1), end_date=TODAY + timedelta(days=project_deadline_days))
    db_session.add_all([a1, a2])
    db_session.commit()

    return {"alex": alex, "maya": maya, "p1": p1, "p2": p2, "a1": a1, "a2": a2,
           "lars": people[2] if add_external_candidate else None}


def test_facts_include_reassign_and_move_delivery_when_no_external_fits(db_session):
    """A narrow window (the urgent project itself) that an external candidate's
    lead time can't fit -- reassign and move_delivery are still both offered."""
    ctx = _seed_conflict(db_session)
    facts = _build_conflict_facts(db_session, ctx["alex"].id, ctx["p1"].id)
    kinds = {opt["kind"] for opt in facts["options"]}
    assert "reassign" in kinds
    assert "move_delivery" in kinds
    assert facts["options"][0]["label"] == "A"


def test_facts_include_all_three_when_external_lead_time_fits(db_session):
    """A wider window (the overlapping project) that Lars's 5-day lead time does
    fit -- all three options, cost priced on the days he'd actually be engaged."""
    ctx = _seed_conflict(db_session, project_deadline_days=14)
    facts = _build_conflict_facts(db_session, ctx["alex"].id, ctx["p2"].id)
    kinds = [opt["kind"] for opt in facts["options"]]
    assert kinds == ["reassign", "engage_external", "move_delivery"]

    engage = next(o for o in facts["options"] if o["kind"] == "engage_external")
    assert engage["to_person_id"] == ctx["lars"].id
    # available_from (lead-time-adjusted) through the window end, NOT the full
    # original window -- the bug this test guards against priced 14 days when
    # only 6 were actually engageable.
    assert engage["start_date"] > ctx["a2"].start_date.isoformat()
    assert engage["end_date"] == ctx["a2"].end_date.isoformat()
    assert "€" in engage["detail"]


def test_facts_exclude_external_candidate_whose_lead_time_does_not_fit(db_session):
    ctx = _seed_conflict(db_session, project_deadline_days=14)
    facts = _build_conflict_facts(db_session, ctx["alex"].id, ctx["p1"].id)  # the narrow window
    kinds = {opt["kind"] for opt in facts["options"]}
    assert "engage_external" not in kinds


def test_reassign_candidate_with_partial_headroom_is_not_wrongly_excluded(db_session):
    """Regression: a candidate with an overlapping-but-partial commitment (enough
    spare capacity for the whole window) must not be treated as 'busy until that
    commitment ends' -- Maya at 45%/100% has exactly the 40% this transfer needs,
    for the whole window, immediately."""
    ctx = _seed_conflict(db_session, add_external_candidate=False)
    # Maya already has an unrelated, overlapping-but-partial commitment.
    db_session.add(Assignment(project_id=ctx["p1"].id, person_id=ctx["maya"].id, allocation_pct=45,
                              start_date=TODAY - timedelta(days=10), end_date=TODAY + timedelta(days=30)))
    db_session.commit()

    facts = _build_conflict_facts(db_session, ctx["alex"].id, ctx["p2"].id)
    reassign = next(o for o in facts["options"] if o["kind"] == "reassign")
    assert reassign["to_person_id"] == ctx["maya"].id
    assert reassign["start_date"] == TODAY.isoformat()  # available immediately


def test_reassign_prefers_more_headroom_and_names_the_runner_up(db_session):
    """REVIEW_03.md R2.4: among candidates who already qualify, the one with
    more spare capacity wins, and the option's detail names the runner-up's
    own headroom -- not just "spare capacity" with no comparison."""
    ctx = _seed_conflict(db_session, project_deadline_days=14, add_external_candidate=False)
    # A second qualifying candidate, sharing Maya's skill, with less headroom.
    priya = Person(name="Priya", role=PersonRole.designer, capacity_pct=100, skills="layout",
                  is_external=False)
    db_session.add(priya)
    db_session.flush()
    db_session.add_all([
        # Maya: 45% committed elsewhere -> 55% free.
        Assignment(project_id=ctx["p1"].id, person_id=ctx["maya"].id, allocation_pct=45,
                  start_date=TODAY - timedelta(days=10), end_date=TODAY + timedelta(days=30)),
        # Priya: 60% committed elsewhere -> 40% free, still enough for this transfer (40%).
        Assignment(project_id=ctx["p1"].id, person_id=priya.id, allocation_pct=60,
                  start_date=TODAY - timedelta(days=10), end_date=TODAY + timedelta(days=30)),
    ])
    db_session.commit()

    facts = _build_conflict_facts(db_session, ctx["alex"].id, ctx["p2"].id)
    reassign = next(o for o in facts["options"] if o["kind"] == "reassign")
    assert reassign["to_person_id"] == ctx["maya"].id
    assert "55% free" in reassign["detail"]
    assert "against Priya's 40%" in reassign["detail"]


def test_route_recommend_persists_the_real_computed_options(client, db_session):
    ctx = _seed_conflict(db_session, project_deadline_days=14)
    resp = client.post("/resources/recommend", data={"person_id": ctx["alex"].id, "project_id": ctx["p2"].id})
    assert resp.status_code == 200

    rec = db_session.query(Recommendation).filter_by(kind=RecommendationKind.resource_reallocation).one()
    payload = json.loads(rec.payload_json)
    assert [o["kind"] for o in payload["options"]] == ["reassign", "engage_external", "move_delivery"]
    assert payload["recommended_label"] in {o["label"] for o in payload["options"]}


def test_accept_option_a_reassigns_internally(client, db_session):
    ctx = _seed_conflict(db_session, project_deadline_days=14)
    client.post("/resources/recommend", data={"person_id": ctx["alex"].id, "project_id": ctx["p2"].id})
    rec = db_session.query(Recommendation).filter_by(kind=RecommendationKind.resource_reallocation).one()

    resp = client.post(f"/recommendations/{rec.id}/accept", data={"option_label": "A"})
    assert resp.status_code == 200

    db_session.refresh(ctx["a2"])
    assert ctx["a2"].person_id == ctx["maya"].id
    assert get_conflicts(db_session, on_date=TODAY) == [] or ctx["alex"].id not in \
        {c.person.id for c in get_conflicts(db_session, on_date=TODAY)}


def test_accept_option_b_engages_lars_with_the_adjusted_window(client, db_session):
    """Regression: accepting engage_external used to apply the ORIGINAL
    assignment's dates, which could start before the external candidate's lead
    time allowed -- refusing an engagement the recommendation itself had just
    said was feasible."""
    ctx = _seed_conflict(db_session, project_deadline_days=14)
    client.post("/resources/recommend", data={"person_id": ctx["alex"].id, "project_id": ctx["p2"].id})
    rec = db_session.query(Recommendation).filter_by(kind=RecommendationKind.resource_reallocation).one()
    payload = json.loads(rec.payload_json)
    engage = next(o for o in payload["options"] if o["kind"] == "engage_external")

    resp = client.post(f"/recommendations/{rec.id}/accept", data={"option_label": "B"})
    assert resp.status_code == 200

    db_session.refresh(rec)
    assert "Could not engage" not in rec.outcome_note

    lars_assignment = db_session.query(Assignment).filter_by(person_id=ctx["lars"].id).one()
    assert lars_assignment.start_date == date.fromisoformat(engage["start_date"])
    assert lars_assignment.start_date > ctx["a2"].start_date  # NOT the original (too-early) start

    mid_engagement = lars_assignment.start_date + timedelta(days=1)
    on_roster = {c.person.id for c in all_person_capacities(db_session, on_date=mid_engagement)}
    assert ctx["lars"].id in on_roster


def test_accept_option_c_moves_delivery_and_shifts_the_assignment(client, db_session):
    ctx = _seed_conflict(db_session, project_deadline_days=14)
    client.post("/resources/recommend", data={"person_id": ctx["alex"].id, "project_id": ctx["p2"].id})
    rec = db_session.query(Recommendation).filter_by(kind=RecommendationKind.resource_reallocation).one()
    payload = json.loads(rec.payload_json)
    move = next(o for o in payload["options"] if o["kind"] == "move_delivery")
    expected_deadline = date.fromisoformat(move["new_deadline"])
    original_deadline = ctx["p2"].deadline
    shift = (expected_deadline - original_deadline).days

    resp = client.post(f"/recommendations/{rec.id}/accept", data={"option_label": "C"})
    assert resp.status_code == 200

    db_session.refresh(ctx["p2"])
    db_session.refresh(ctx["a2"])
    assert ctx["p2"].deadline == expected_deadline
    assert ctx["a2"].start_date == (TODAY - timedelta(days=1)) + timedelta(days=shift)
    assert ctx["a2"].end_date == original_deadline + timedelta(days=shift)
    # The conflict this was meant to resolve is actually gone, not just relabelled.
    assert ctx["alex"].id not in {c.person.id for c in get_conflicts(db_session, on_date=TODAY)}


def test_accept_falls_back_to_the_recommended_label_if_none_posted(client, db_session):
    ctx = _seed_conflict(db_session, project_deadline_days=14)
    client.post("/resources/recommend", data={"person_id": ctx["alex"].id, "project_id": ctx["p2"].id})
    rec = db_session.query(Recommendation).filter_by(kind=RecommendationKind.resource_reallocation).one()
    payload = json.loads(rec.payload_json)

    resp = client.post(f"/recommendations/{rec.id}/accept")  # no option_label at all
    assert resp.status_code == 200

    db_session.refresh(rec)
    recommended = next(o for o in payload["options"] if o["label"] == payload["recommended_label"])
    assert recommended["action"] in rec.outcome_note or recommended["kind"] == "move_delivery"
