from app.models import PersonRole, PhaseKind, PhaseTemplate, ProjectType
from app.seed import PHASE_TEMPLATES, seed_phase_templates

EXPECTED_PHASE_COUNTS = {
    "Film / branded content": 14,
    "Event": 9,
    "Stills": 9,
    "Social / AI-generated content": 11,
}

EXPECTED_TOTAL_DAYS = {
    "Film / branded content": 35,
    "Event": 27,
    "Stills": 17,
    "Social / AI-generated content": 11,
}


def test_seeds_one_project_type_per_template_with_expected_phase_counts(db_session):
    seed_phase_templates(db_session)

    types = db_session.query(ProjectType).all()
    assert {t.name for t in types} == set(EXPECTED_PHASE_COUNTS)

    for project_type in types:
        phases = (
            db_session.query(PhaseTemplate)
            .filter_by(project_type_id=project_type.id)
            .all()
        )
        assert len(phases) == EXPECTED_PHASE_COUNTS[project_type.name]
        assert sum(p.default_days for p in phases) == EXPECTED_TOTAL_DAYS[project_type.name]


def test_phase_sequence_is_contiguous_starting_at_one(db_session):
    seed_phase_templates(db_session)

    for project_type in db_session.query(ProjectType).all():
        phases = (
            db_session.query(PhaseTemplate)
            .filter_by(project_type_id=project_type.id)
            .order_by(PhaseTemplate.sequence)
            .all()
        )
        assert [p.sequence for p in phases] == list(range(1, len(phases) + 1))


def test_milestones_are_zero_duration(db_session):
    seed_phase_templates(db_session)

    milestones = db_session.query(PhaseTemplate).filter_by(is_milestone=True).all()
    assert len(milestones) > 0
    assert all(p.default_days == 0 for p in milestones)


def test_required_roles_are_valid_person_roles(db_session):
    seed_phase_templates(db_session)

    valid_roles = {r.value for r in PersonRole}
    for phase in db_session.query(PhaseTemplate).all():
        roles = phase.required_roles.split(",")
        assert roles, f"{phase.name} has no required roles"
        assert set(roles) <= valid_roles, f"{phase.name} has an unrecognised role in {roles}"


def test_kind_is_never_the_literal_string_milestone(db_session):
    # PLANNING.md's own phase tables list "milestone" as a Kind value for three rows, which
    # isn't one of the four kinds that same doc defines — is_milestone carries that instead.
    seed_phase_templates(db_session)

    for phase in db_session.query(PhaseTemplate).all():
        assert phase.kind in list(PhaseKind)


def test_phase_templates_dict_matches_what_gets_seeded(db_session):
    seed_phase_templates(db_session)

    for type_name, (_, phases) in PHASE_TEMPLATES.items():
        project_type = db_session.query(ProjectType).filter_by(name=type_name).one()
        stored = (
            db_session.query(PhaseTemplate)
            .filter_by(project_type_id=project_type.id)
            .order_by(PhaseTemplate.sequence)
            .all()
        )
        assert len(stored) == len(phases)
        for row, template in zip(stored, phases):
            assert row.name == template[1]
            assert row.default_days == template[2]
