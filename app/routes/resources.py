import json
from datetime import date, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.templates_env import templates
from app.models import (
    Assignment,
    Person,
    PersonRole,
    Project,
    RateBand,
    Recommendation,
    RecommendationKind,
    RecommendationStatus,
)
from app.services.ai.resource import recommend_resource
from app.services.assignment import earliest_feasible_start, engage_person
from app.services.capacity import (
    all_person_capacities,
    available_pct,
    get_conflicts,
    is_actively_engaged,
    peak_allocation_pct,
)

router = APIRouter()

# REVIEW_02.md P5.5: default engagement length offered on the Talent Pool form —
# a starting point a producer adjusts, not a constraint engage_person() enforces.
DEFAULT_ENGAGEMENT_DAYS = 5


def _screen_context(db: Session):
    today = date.today()
    capacities = all_person_capacities(db, on_date=today)
    conflicts = get_conflicts(db, on_date=today)

    projects_by_id = {p.id: p for p in db.query(Project).all()}
    all_assignments = db.query(Assignment).all()

    # REVIEW_02.md P5.1: project ids, not pre-joined name strings — the template
    # needs the id to link each one, which a flattened "name, name, name" string
    # discards before it ever reaches Jinja.
    current_assignments: dict[int, list[int]] = {}
    for pc in capacities:
        person_assignments = [
            a for a in all_assignments
            if a.person_id == pc.person.id and a.start_date <= today <= a.end_date
        ]
        current_assignments[pc.person.id] = [
            a.project_id for a in person_assignments if a.project_id in projects_by_id
        ]

    # For each conflict, the project with the soonest deadline is the one worth
    # reassigning — moving it off the overloaded person is what protects that date.
    conflict_targets = {}
    for c in conflicts:
        soonest = min(c.projects, key=lambda p: p.deadline)
        conflict_targets[c.person.id] = soonest

    # REVIEW_02.md P5.5: an engaged pool member's current engagement end date, so
    # the table can show it "visibly marked as external with an end date" rather
    # than reading like a permanent Team row.
    engagement_end_by_person_id: dict[int, date] = {}
    for pc in capacities:
        if not pc.person.is_external:
            continue
        current = [a for a in all_assignments
                  if a.person_id == pc.person.id and a.start_date <= today <= a.end_date]
        if current:
            engagement_end_by_person_id[pc.person.id] = max(a.end_date for a in current)

    # REVIEW_02.md P5.5: "the ability to bring in external resource of any role, on
    # demand" — every external person NOT currently engaged, with the rate and lead
    # time their role carries in the Assumptions library (RateBand). Not shown on
    # the main table above (all_person_capacities already excludes them for exactly
    # this reason — "not on the capacity roster until engaged").
    rate_bands_by_role = {rb.role: rb for rb in db.query(RateBand).all()}
    talent_pool = []
    for person in db.query(Person).filter_by(is_external=True).all():
        person_assignments = [a for a in all_assignments if a.person_id == person.id]
        if is_actively_engaged(person, person_assignments, today):
            continue
        rate_band = rate_bands_by_role.get(person.role)
        talent_pool.append({
            "person": person,
            "rate_band": rate_band,
            "earliest_start": earliest_feasible_start(db, person, today),
        })

    recommendations = (
        db.query(Recommendation)
        .filter_by(kind=RecommendationKind.resource_reallocation)
        .order_by(Recommendation.created_at.desc())
        .all()
    )
    recommendations_view = [
        {"rec": rec, "payload": json.loads(rec.payload_json)} for rec in recommendations
    ]
    people_by_id = {p.id: p for p in db.query(Person).all()}

    return {
        "capacities": capacities,
        "conflicts": conflicts,
        "current_assignments": current_assignments,
        "engagement_end_by_person_id": engagement_end_by_person_id,
        "conflict_targets": conflict_targets,
        "recommendations": recommendations_view,
        "people_by_id": people_by_id,
        "projects_by_id": projects_by_id,
        "talent_pool": talent_pool,
        "active_projects": [p for p in projects_by_id.values() if p.status.value not in
                            ("delivered", "on_hold", "cancelled", "archived")],
        "default_engagement_end": today + timedelta(days=DEFAULT_ENGAGEMENT_DAYS),
    }


@router.get("/resources")
def resources(request: Request, error: str | None = None, info: str | None = None,
             engage_error: str | None = None, db: Session = Depends(get_db)):
    context = _screen_context(db)
    context["recommend_failed"] = error == "recommend_failed"
    context["recommendation_unchanged"] = info == "recommendation_unchanged"
    context["engage_error"] = engage_error
    return templates.TemplateResponse(request, "resources.html", context)


@router.post("/resources/engage")
def engage(person_id: int = Form(...), project_id: int = Form(...),
          start_date: date = Form(...), end_date: date = Form(...),
          allocation_pct: int = Form(...), db: Session = Depends(get_db)):
    """REVIEW_02.md P5.5: the Talent Pool's own engage action — 'the ability to
    bring in external resource of any role, on demand.' Routes through the same
    engage_person() Timeline and Localisation use (P5.5's 'one mechanism, three
    screens'), so the same capacity and lead-time rules apply here too."""
    person = db.get(Person, person_id)
    project = db.get(Project, project_id)
    if person is None or project is None or end_date < start_date:
        return RedirectResponse(url="/resources?engage_error=Invalid+engagement", status_code=303)

    existing = (
        db.query(Assignment)
        .filter_by(project_id=project_id, person_id=person_id, project_phase_id=None)
        .first()
    )
    assignment, refusal = engage_person(
        db, person, project_id=project_id, start_date=start_date, end_date=end_date,
        allocation_pct=allocation_pct, existing_id=existing.id if existing is not None else None,
    )
    if assignment is None:
        return RedirectResponse(url=f"/resources?engage_error={quote(refusal)}", status_code=303)

    db.commit()
    return RedirectResponse(url="/resources", status_code=303)


# A producer coordinates rather than produces, and a translator does language
# work — neither is a plausible substitute for reassigned creative production
# work, regardless of spare capacity or an incidental skill-tag overlap.
_INELIGIBLE_CANDIDATE_ROLES = {PersonRole.producer, PersonRole.translator}


def _candidate_available_from(db: Session, person: Person, window_start: date, today: date) -> date:
    """REVIEW_02.md P5.6: the date this candidate is actually free from, for the
    "available <date>" line. The candidate has already passed the spare-capacity
    check for the *entire* transfer window (peak_allocation_pct, below) before this
    is ever called — a partially-loaded person with enough headroom the whole time
    (e.g. someone at 45% with the 55% this transfer needs) is available now, not
    "once their other assignment ends"; that other assignment was never in the way.
    earliest_feasible_start() is the one thing that actually gates a start date:
    today for internal people, lead-time-adjusted for external."""
    return max(earliest_feasible_start(db, person, today), window_start)


def _build_conflict_facts(db: Session, person_id: int, project_id: int) -> dict | None:
    today = date.today()
    overloaded = db.get(Person, person_id)
    project = db.get(Project, project_id)
    if overloaded is None or project is None:
        return None

    transfer_assignment = (
        db.query(Assignment).filter_by(person_id=person_id, project_id=project_id).first()
    )
    if transfer_assignment is None:
        return None
    transfer_pct = transfer_assignment.allocation_pct
    window_start = transfer_assignment.start_date
    window_end = transfer_assignment.end_date
    window_days = (window_end - window_start).days + 1

    overloaded_assignments = db.query(Assignment).filter_by(person_id=person_id).all()
    overloaded_allocated = peak_allocation_pct(overloaded_assignments, today)
    overloaded_skills = set(s.strip() for s in overloaded.skills.split(",") if s.strip())

    rate_bands_by_role = {rb.role: rb for rb in db.query(RateBand).all()}

    # REVIEW_02.md P5.6: "a real decision has alternatives with different costs."
    # Every candidate this app already knows how to evaluate — Team (reassign) and
    # Talent Pool (engage externally, REVIEW_02.md P5.5) — considered on the same
    # terms: enough spare capacity across the transfer window, ineligible roles
    # (producer, translator) excluded either way.
    internal_candidates, external_candidates = [], []
    for person in db.query(Person).all():
        if person.id == person_id or person.role in _INELIGIBLE_CANDIDATE_ROLES:
            continue
        person_assignments = db.query(Assignment).filter_by(person_id=person.id).all()
        allocated = peak_allocation_pct(person_assignments, today)
        available = available_pct(person.capacity_pct, allocated)
        if available < transfer_pct:
            continue  # not feasible — Python filters before the model ever sees it
        available_from = _candidate_available_from(db, person, window_start, today)
        if available_from > window_end:
            continue  # can't start in time to do any of this work
        person_skills = set(s.strip() for s in person.skills.split(",") if s.strip())
        entry = {
            "id": person.id,
            "name": person.name,
            "role": person.role.value,
            "allocated_pct": allocated,
            "available_pct": available,
            "available_from": available_from.isoformat(),
            "skills": sorted(person_skills),
            "matches_skill": bool(overloaded_skills & person_skills),
            "is_external": person.is_external,
        }
        (external_candidates if person.is_external else internal_candidates).append(entry)

    def _best(pool: list[dict]) -> dict | None:
        skill_matches = [c for c in pool if c["matches_skill"]]
        chosen_pool = skill_matches or pool
        return min(chosen_pool, key=lambda c: (c["available_from"], -c["available_pct"])) if chosen_pool else None

    options = []
    best_internal = _best(internal_candidates)
    if best_internal is not None:
        options.append({
            "label": "", "kind": "reassign",
            "action": f"Reassign to {best_internal['name']}",
            "detail": (
                f"no cost, available {best_internal['available_from']}"
                f"{', has worked this brand before' if best_internal['matches_skill'] else ', has not worked this brand before'}"
            ),
            "to_person_id": best_internal["id"],
            "start_date": best_internal["available_from"], "end_date": window_end.isoformat(),
            "new_deadline": None,
        })

    best_external = _best(external_candidates)
    if best_external is not None:
        # Lead time can eat into the window — the engageable stretch is from
        # whenever they can actually start through the same window end, not the
        # full original duration, and cost must be priced on the days they'd
        # actually be engaged for, not the days the overloaded person was.
        engaged_start = date.fromisoformat(best_external["available_from"])
        engaged_days = (window_end - engaged_start).days + 1
        rate_band = rate_bands_by_role.get(PersonRole(best_external["role"]))
        day_rate = round((rate_band.low + rate_band.high) / 2) if rate_band else None
        lead_time = rate_band.lead_time_days if rate_band else 0
        cost_note = f"€{day_rate}/day × {engaged_days} day{'s' if engaged_days != 1 else ''}" if day_rate else "rate not set"
        options.append({
            "label": "", "kind": "engage_external",
            "action": f"Engage {best_external['name']} (external, {best_external['role'].replace('_', ' ')})",
            "detail": f"{cost_note}, {lead_time}-day lead time, available {best_external['available_from']}",
            "to_person_id": best_external["id"],
            "start_date": best_external["available_from"], "end_date": window_end.isoformat(),
            "new_deadline": None,
        })

    # Always computable, unlike the two above: how many days the transfer
    # assignment's own start would need to move to clear whichever of the
    # overloaded person's OTHER assignments it currently overlaps — the real
    # cause of the conflict. Assumes the deadline (and this assignment) shift
    # together by that many days; accepting this option moves both.
    overlapping_others = [
        a for a in overloaded_assignments
        if a.id != transfer_assignment.id and a.start_date <= window_end and a.end_date >= window_start
    ]
    if overlapping_others:
        shift_days = max((a.end_date - window_start).days + 1 for a in overlapping_others)
        options.append({
            "label": "", "kind": "move_delivery",
            "action": f"Move delivery to {(project.deadline + timedelta(days=shift_days)).strftime('%d %b')}",
            "detail": "no cost, no resource change, client conversation required",
            "to_person_id": None, "new_deadline": (project.deadline + timedelta(days=shift_days)).isoformat(),
        })

    if not options:
        return None
    for label, opt in zip("ABC", options):
        opt["label"] = label

    return {
        "project_id": project.id,
        # REVIEW_02.md P3: accepting the recommendation must move exactly this
        # Assignment row, not "whichever one matches (project_id, person_id) first"
        # — a person can hold more than one assignment on the same project (a
        # whole-project one plus one or more phase-derived ones), and only this ID
        # disambiguates which is being reassigned.
        "assignment_id": transfer_assignment.id,
        "project_name": project.name,
        "deadline": project.deadline.isoformat(),
        "overloaded_person": {
            "id": overloaded.id,
            "name": overloaded.name,
            "capacity_pct": overloaded.capacity_pct,
            "allocated_pct": overloaded_allocated,
        },
        "transfer_allocation_pct": transfer_pct,
        "options": options,
    }


@router.post("/resources/recommend")
def recommend(request: Request, person_id: int = Form(...), project_id: int = Form(...),
              db: Session = Depends(get_db)):
    facts = _build_conflict_facts(db, person_id, project_id)
    if facts is None:
        return RedirectResponse(url="/resources?error=recommend_failed", status_code=303)

    # FEEDBACK_LOG.md A4: requesting a recommendation for a conflict that
    # already has a pending one replaces it rather than appending — but only
    # if the underlying facts actually changed. If nothing has changed, don't
    # silently re-run the model; say so and leave the existing one in place.
    existing = (
        db.query(Recommendation)
        .filter_by(kind=RecommendationKind.resource_reallocation, project_id=project_id,
                  status=RecommendationStatus.pending)
        .first()
    )
    if existing is not None and json.loads(existing.computed_facts_json) == facts:
        return RedirectResponse(url="/resources?info=recommendation_unchanged", status_code=303)

    rec = recommend_resource(facts)
    if rec is None:
        return RedirectResponse(url="/resources?error=recommend_failed", status_code=303)

    if existing is not None:
        db.delete(existing)
        db.flush()

    db.add(Recommendation(
        kind=RecommendationKind.resource_reallocation,
        project_id=project_id,
        payload_json=rec.model_dump_json(),
        rationale=rec.rationale,
        computed_facts_json=json.dumps(facts, default=str),
        status=RecommendationStatus.pending,
    ))
    db.commit()
    return RedirectResponse(url="/resources", status_code=303)
