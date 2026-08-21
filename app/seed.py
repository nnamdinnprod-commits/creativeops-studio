"""Idempotent demo data seed, per docs/DEMO_DATA.md.

Run with `python -m app.seed` to seed (skips if data already exists).
Run with `python -m app.seed --reset` to wipe and reseed from a clean state.
"""

import sys
from datetime import date, timedelta

from app.database import Base, SessionLocal, engine
from app.models import (
    Assignment,
    CreativeInsight,
    Deliverable,
    DeliverableStatus,
    DeliverableType,
    Localisation,
    LocalisationStatus,
    Person,
    PersonRole,
    Priority,
    Project,
    ProjectStatus,
    SubStatus,
    VariantTheme,
)

TODAY = date.today()


def this_or_next_friday(from_date: date) -> date:
    return from_date + timedelta(days=(4 - from_date.weekday()) % 7)


def seed(session):
    # --- People ---
    alex = Person(name="Alex", role=PersonRole.senior_designer, capacity_pct=80,
                  skills="layout,retouching,paid_formats", is_external=False)
    maya = Person(name="Maya", role=PersonRole.designer, capacity_pct=100,
                  skills="layout,retouching", is_external=False)
    sam = Person(name="Sam", role=PersonRole.producer, capacity_pct=100,
                 skills="", is_external=False)
    elena = Person(name="Elena", role=PersonRole.motion_designer, capacity_pct=80,
                   skills="motion,paid_formats", is_external=False)
    tomas = Person(name="Tomas", role=PersonRole.copywriter, capacity_pct=60,
                   skills="copy_de,copy_fr", is_external=False)
    priya = Person(name="Priya", role=PersonRole.designer, capacity_pct=100,
                   skills="layout,paid_formats", is_external=False)
    jonas = Person(name="Jonas", role=PersonRole.translator, capacity_pct=100,
                   skills="copy_de", is_external=True)
    camille = Person(name="Camille", role=PersonRole.translator, capacity_pct=100,
                     skills="copy_fr", is_external=True)
    people = [alex, maya, sam, elena, tomas, priya, jonas, camille]
    session.add_all(people)
    session.flush()  # assign ids

    friday = this_or_next_friday(TODAY)

    # --- Projects ---
    p1 = Project(name="Winter Campaign Refresh", brand="Albelli", campaign="Winter 2026",
                 source_market="NL", priority=Priority.high, status=ProjectStatus.in_production,
                 deadline=friday, owner_id=sam.id,
                 brief_raw="Refresh winter hero creative across NL, DE, FR and ES paid social and homepage.",
                 localisation_required=True, estimated_days=4.0)
    p2 = Project(name="Loyalty Relaunch Teaser", brand="Photobox", campaign="Loyalty Relaunch",
                 source_market="UK", priority=Priority.medium, status=ProjectStatus.assigned,
                 deadline=TODAY + timedelta(days=10), owner_id=sam.id,
                 brief_raw="Teaser assets for loyalty programme relaunch, UK, ES and DE paid social.",
                 localisation_required=True, estimated_days=3.0)
    p3 = Project(name="Spring Lookbook", brand="Hofmann", campaign="Spring 2026",
                 source_market="ES", priority=Priority.medium, status=ProjectStatus.assigned,
                 deadline=TODAY + timedelta(days=15), owner_id=sam.id,
                 brief_raw="Spring lookbook static set for ES homepage and email, extending to DE and FR.",
                 localisation_required=True, estimated_days=5.0)
    p4 = Project(name="Loyalty App Push", brand="Hofmann", campaign="App Growth",
                 source_market="DE", priority=Priority.medium, status=ProjectStatus.brief,
                 deadline=friday, owner_id=sam.id,
                 brief_raw=(
                     "Need something for the DE app push, ideally next Friday. Probably social "
                     "and maybe email? Not sure on exact sizes yet, will confirm. Audience is "
                     "existing customers I think. Who signs off on this one is TBC."
                 ),
                 localisation_required=False, estimated_days=None)
    p5 = Project(name="Autumn Prints FR Push", brand="Photobox", campaign="Autumn Prints",
                 source_market="UK", priority=Priority.high, status=ProjectStatus.in_production,
                 deadline=TODAY + timedelta(days=10), owner_id=sam.id,
                 brief_raw="Autumn prints campaign extending to the French market.",
                 localisation_required=True, estimated_days=4.0)
    p6 = Project(name="Retouch Guidelines Refresh", brand="Albelli", campaign="Brand Ops",
                 source_market="NL", priority=Priority.low, status=ProjectStatus.brief,
                 deadline=TODAY + timedelta(days=21), owner_id=sam.id,
                 brief_raw="Update internal retouching guidelines deck for design team onboarding.",
                 localisation_required=False, estimated_days=None)
    p7 = Project(name="Mother's Day Static Set", brand="Photobox", campaign="Mothers Day",
                 source_market="UK", priority=Priority.medium, status=ProjectStatus.ready,
                 deadline=TODAY + timedelta(days=24), owner_id=sam.id,
                 brief_raw="Mother's Day social static set, UK and ES, 6 variants, 1080x1080, "
                           "approved by Sam, audience existing + prospecting customers.",
                 localisation_required=True, estimated_days=3.0)
    p8 = Project(name="Photobook Bundle Homepage Banner", brand="Albelli", campaign="Bundle Promo",
                 source_market="NL", priority=Priority.medium, status=ProjectStatus.ready,
                 deadline=TODAY + timedelta(days=18), owner_id=sam.id,
                 brief_raw="Homepage banner for photobook bundle promo, NL and DE, approved "
                           "by Sam, 1600x400 spec confirmed.",
                 localisation_required=True, estimated_days=2.0)
    p9 = Project(name="Calendar Season Kickoff", brand="Hofmann", campaign="Calendar 2027",
                 source_market="ES", priority=Priority.high, status=ProjectStatus.assigned,
                 deadline=TODAY + timedelta(days=12), owner_id=sam.id,
                 brief_raw="Calendar season kickoff creative, ES and FR paid social.",
                 localisation_required=True, estimated_days=4.0)
    p10 = Project(name="Gift Card Email Series", brand="Photobox", campaign="Gift Cards",
                  source_market="UK", priority=Priority.medium, status=ProjectStatus.creative_review,
                  deadline=TODAY + timedelta(days=6), owner_id=sam.id,
                  brief_raw="3-part gift card email series, UK, NL and DE, in creative review.",
                  localisation_required=True, estimated_days=2.5)
    p11 = Project(name="Canvas Prints Paid Display", brand="Albelli", campaign="Canvas Push",
                  source_market="NL", priority=Priority.medium, status=ProjectStatus.approved,
                  deadline=TODAY + timedelta(days=4), owner_id=sam.id,
                  brief_raw="Paid display set for canvas prints, NL and DE and FR, approved and awaiting delivery.",
                  localisation_required=True, estimated_days=3.0)
    p12 = Project(name="New Year Cards Social Set", brand="Hofmann", campaign="New Year",
                  source_market="DE", priority=Priority.low, status=ProjectStatus.delivered,
                  deadline=TODAY - timedelta(days=10), owner_id=sam.id,
                  brief_raw="New Year cards social set, DE with FR extension, delivered on schedule.",
                  localisation_required=True, estimated_days=2.0)
    projects = [p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12]
    session.add_all(projects)
    session.flush()

    # --- Assignments (capacity conflicts live here) ---
    # Alex: overloaded to ~95% via two overlapping assignments, one deadline this week.
    a1 = Assignment(project_id=p1.id, person_id=alex.id, allocation_pct=55,
                    start_date=TODAY - timedelta(days=5), end_date=friday,
                    role_on_project="lead designer")
    a2 = Assignment(project_id=p2.id, person_id=alex.id, allocation_pct=40,
                    start_date=TODAY - timedelta(days=3), end_date=TODAY + timedelta(days=10),
                    role_on_project="designer")
    # Maya: 45% committed elsewhere, leaving enough headroom to take over p1 from Alex.
    a3 = Assignment(project_id=p3.id, person_id=maya.id, allocation_pct=45,
                    start_date=TODAY - timedelta(days=8), end_date=TODAY + timedelta(days=15),
                    role_on_project="designer")
    # Elena: two overlapping but non-overloading assignments (genuine overlap, no conflict).
    a4 = Assignment(project_id=p5.id, person_id=elena.id, allocation_pct=30,
                    start_date=TODAY - timedelta(days=2), end_date=TODAY + timedelta(days=10),
                    role_on_project="motion designer")
    a5 = Assignment(project_id=p9.id, person_id=elena.id, allocation_pct=40,
                    start_date=TODAY, end_date=TODAY + timedelta(days=12),
                    role_on_project="motion designer")
    # Remaining projects staffed for realism.
    a6 = Assignment(project_id=p7.id, person_id=priya.id, allocation_pct=50,
                    start_date=TODAY, end_date=TODAY + timedelta(days=24),
                    role_on_project="designer")
    a7 = Assignment(project_id=p8.id, person_id=priya.id, allocation_pct=30,
                    start_date=TODAY, end_date=TODAY + timedelta(days=18),
                    role_on_project="designer")
    a8 = Assignment(project_id=p9.id, person_id=tomas.id, allocation_pct=25,
                    start_date=TODAY, end_date=TODAY + timedelta(days=12),
                    role_on_project="copywriter")
    a9 = Assignment(project_id=p10.id, person_id=tomas.id, allocation_pct=20,
                    start_date=TODAY - timedelta(days=4), end_date=TODAY + timedelta(days=6),
                    role_on_project="copywriter")
    a10 = Assignment(project_id=p11.id, person_id=sam.id, allocation_pct=15,
                     start_date=TODAY - timedelta(days=6), end_date=TODAY + timedelta(days=4),
                     role_on_project="producer")
    session.add_all([a1, a2, a3, a4, a5, a6, a7, a8, a9, a10])

    # --- Deliverables ---
    deliverables = [
        Deliverable(project_id=p1.id, type=DeliverableType.social_static, market="NL",
                   format_spec="1080x1080", status=DeliverableStatus.in_progress, deadline=friday),
        Deliverable(project_id=p1.id, type=DeliverableType.homepage_banner, market="NL",
                   format_spec="1600x400", status=DeliverableStatus.in_progress, deadline=friday),
        Deliverable(project_id=p2.id, type=DeliverableType.social_video, market="UK",
                   format_spec="16:9 15s", status=DeliverableStatus.not_started,
                   deadline=TODAY + timedelta(days=10)),
        Deliverable(project_id=p3.id, type=DeliverableType.social_static, market="ES",
                   format_spec="1080x1080", status=DeliverableStatus.in_progress,
                   deadline=TODAY + timedelta(days=15)),
        Deliverable(project_id=p3.id, type=DeliverableType.email, market="ES",
                   format_spec=None, status=DeliverableStatus.not_started,
                   deadline=TODAY + timedelta(days=15)),
        Deliverable(project_id=p5.id, type=DeliverableType.social_static, market="UK",
                   format_spec="1080x1080", status=DeliverableStatus.in_progress,
                   deadline=TODAY + timedelta(days=10)),
        Deliverable(project_id=p5.id, type=DeliverableType.social_static, market="FR",
                   format_spec="1080x1080", status=DeliverableStatus.not_started,
                   deadline=TODAY + timedelta(days=10)),
        Deliverable(project_id=p5.id, type=DeliverableType.motion, market="UK",
                   format_spec="16:9 15s", status=DeliverableStatus.in_progress,
                   deadline=TODAY + timedelta(days=10)),
        Deliverable(project_id=p7.id, type=DeliverableType.social_static, market="UK",
                   format_spec="1080x1080", status=DeliverableStatus.not_started,
                   deadline=TODAY + timedelta(days=24)),
        Deliverable(project_id=p7.id, type=DeliverableType.social_static, market="ES",
                   format_spec="1080x1080", status=DeliverableStatus.not_started,
                   deadline=TODAY + timedelta(days=24)),
        Deliverable(project_id=p8.id, type=DeliverableType.homepage_banner, market="NL",
                   format_spec="1600x400", status=DeliverableStatus.not_started,
                   deadline=TODAY + timedelta(days=18)),
        Deliverable(project_id=p8.id, type=DeliverableType.homepage_banner, market="DE",
                   format_spec="1600x400", status=DeliverableStatus.not_started,
                   deadline=TODAY + timedelta(days=18)),
        Deliverable(project_id=p9.id, type=DeliverableType.social_static, market="ES",
                   format_spec="1080x1080", status=DeliverableStatus.in_progress,
                   deadline=TODAY + timedelta(days=12)),
        Deliverable(project_id=p9.id, type=DeliverableType.social_static, market="FR",
                   format_spec="1080x1080", status=DeliverableStatus.not_started,
                   deadline=TODAY + timedelta(days=12)),
        Deliverable(project_id=p9.id, type=DeliverableType.motion, market="ES",
                   format_spec="16:9 15s", status=DeliverableStatus.in_progress,
                   deadline=TODAY + timedelta(days=12)),
        Deliverable(project_id=p10.id, type=DeliverableType.email, market="UK",
                   format_spec=None, status=DeliverableStatus.in_review,
                   deadline=TODAY + timedelta(days=6)),
        Deliverable(project_id=p11.id, type=DeliverableType.paid_display, market="NL",
                   format_spec="300x250", status=DeliverableStatus.approved,
                   deadline=TODAY + timedelta(days=4)),
        Deliverable(project_id=p12.id, type=DeliverableType.social_static, market="DE",
                   format_spec="1080x1080", status=DeliverableStatus.delivered,
                   deadline=TODAY - timedelta(days=10)),
    ]
    session.add_all(deliverables)

    # --- Localisation ---
    # Most projects roll out across several markets, which is where the ~20-row scale
    # comes from. Jonas (DE) and Camille (FR) are the only translator vendors in the
    # roster, per DEMO_DATA.md — ES/NL target rows are honestly left unassigned rather
    # than inventing a vendor that isn't in the seed cast, but their due dates are far
    # enough out that this doesn't falsely trigger the at-risk rule.
    localisations = [
        # P1 — Winter Campaign Refresh (in production, deadline this week)
        Localisation(project_id=p1.id, target_market="DE", language="de",
                    translator_id=jonas.id, status=LocalisationStatus.in_translation,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=friday + timedelta(days=2)),
        Localisation(project_id=p1.id, target_market="FR", language="fr",
                    translator_id=camille.id, status=LocalisationStatus.in_translation,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=friday + timedelta(days=2)),
        Localisation(project_id=p1.id, target_market="ES", language="es",
                    translator_id=None, status=LocalisationStatus.not_started,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=friday + timedelta(days=5)),
        # P2 — Loyalty Relaunch Teaser (assigned, work not yet underway)
        Localisation(project_id=p2.id, target_market="ES", language="es",
                    translator_id=None, status=LocalisationStatus.not_started,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=TODAY + timedelta(days=10)),
        Localisation(project_id=p2.id, target_market="DE", language="de",
                    translator_id=None, status=LocalisationStatus.not_started,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=TODAY + timedelta(days=10)),
        # P3 — Spring Lookbook (assigned, work not yet underway)
        Localisation(project_id=p3.id, target_market="DE", language="de",
                    translator_id=None, status=LocalisationStatus.not_started,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=TODAY + timedelta(days=15)),
        Localisation(project_id=p3.id, target_market="FR", language="fr",
                    translator_id=None, status=LocalisationStatus.not_started,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=TODAY + timedelta(days=15)),
        # P5 — Autumn Prints FR Push: the deliberate bottleneck, unchanged.
        Localisation(project_id=p5.id, target_market="FR", language="fr",
                    translator_id=None, status=LocalisationStatus.not_started,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=TODAY + timedelta(days=3)),
        Localisation(project_id=p5.id, target_market="ES", language="es",
                    translator_id=None, status=LocalisationStatus.in_translation,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=TODAY + timedelta(days=10)),
        # P7 — Mother's Day Static Set (ready, not yet in production)
        Localisation(project_id=p7.id, target_market="ES", language="es",
                    translator_id=None, status=LocalisationStatus.not_started,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=TODAY + timedelta(days=24)),
        Localisation(project_id=p7.id, target_market="DE", language="de",
                    translator_id=None, status=LocalisationStatus.not_started,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=TODAY + timedelta(days=24)),
        # P8 — Photobook Bundle Homepage Banner (ready, not yet in production)
        Localisation(project_id=p8.id, target_market="DE", language="de",
                    translator_id=None, status=LocalisationStatus.not_started,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=TODAY + timedelta(days=18)),
        Localisation(project_id=p8.id, target_market="FR", language="fr",
                    translator_id=None, status=LocalisationStatus.not_started,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=TODAY + timedelta(days=18)),
        # P9 — Calendar Season Kickoff (assigned, one market already in review)
        Localisation(project_id=p9.id, target_market="FR", language="fr",
                    translator_id=camille.id, status=LocalisationStatus.in_review,
                    review_status=SubStatus.in_progress, qa_status=SubStatus.pending,
                    due_date=TODAY + timedelta(days=9)),
        Localisation(project_id=p9.id, target_market="DE", language="de",
                    translator_id=None, status=LocalisationStatus.not_started,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=TODAY + timedelta(days=12)),
        # P10 — Gift Card Email Series (creative review, localisation catching up)
        Localisation(project_id=p10.id, target_market="NL", language="nl",
                    translator_id=None, status=LocalisationStatus.not_started,
                    review_status=SubStatus.pending, qa_status=SubStatus.pending,
                    due_date=TODAY + timedelta(days=6)),
        Localisation(project_id=p10.id, target_market="DE", language="de",
                    translator_id=jonas.id, status=LocalisationStatus.qa,
                    review_status=SubStatus.passed, qa_status=SubStatus.in_progress,
                    due_date=TODAY + timedelta(days=6)),
        # P11 — Canvas Prints Paid Display (approved, localisation nearly done)
        Localisation(project_id=p11.id, target_market="DE", language="de",
                    translator_id=jonas.id, status=LocalisationStatus.approved,
                    review_status=SubStatus.passed, qa_status=SubStatus.passed,
                    due_date=TODAY + timedelta(days=4)),
        Localisation(project_id=p11.id, target_market="FR", language="fr",
                    translator_id=camille.id, status=LocalisationStatus.qa,
                    review_status=SubStatus.passed, qa_status=SubStatus.in_progress,
                    due_date=TODAY + timedelta(days=4)),
        # P12 — New Year Cards Social Set (delivered, localisation completed on schedule)
        Localisation(project_id=p12.id, target_market="FR", language="fr",
                    translator_id=camille.id, status=LocalisationStatus.approved,
                    review_status=SubStatus.passed, qa_status=SubStatus.passed,
                    due_date=TODAY - timedelta(days=12)),
    ]
    session.add_all(localisations)

    # --- Creative insights (24 rows; the DE lifestyle-vs-product gap drives the AI recommendation) ---
    insights = []
    de_period_start = TODAY - timedelta(days=30)
    de_period_end = TODAY - timedelta(days=2)
    de_lifestyle_ctrs = [2.1, 2.3, 2.5, 2.6, 2.2, 2.5]
    de_product_ctrs = [1.0, 1.2, 1.1, 0.9, 1.3, 1.1]
    for i, ctr in enumerate(de_lifestyle_ctrs):
        insights.append(CreativeInsight(
            brand=["Albelli", "Photobox", "Hofmann"][i % 3], market="DE", format="social_static",
            variant_theme=VariantTheme.lifestyle, impressions=40000 + i * 3500, ctr=ctr,
            engagement_rate=4.5 + i * 0.2, conversion_rate=1.4 + i * 0.05,
            period_start=de_period_start, period_end=de_period_end,
            insight_text=None,
        ))
    for i, ctr in enumerate(de_product_ctrs):
        insights.append(CreativeInsight(
            brand=["Albelli", "Photobox", "Hofmann"][i % 3], market="DE", format="social_static",
            variant_theme=VariantTheme.product_only, impressions=38000 + i * 3000, ctr=ctr,
            engagement_rate=1.8 + i * 0.15, conversion_rate=0.7 + i * 0.05,
            period_start=de_period_start, period_end=de_period_end,
            insight_text=None,
        ))
    # Padding rows across other markets/themes for realism (12 more, total 24).
    other_rows = [
        ("UK", "paid_display", VariantTheme.promotional, 1.4, 3.0, 1.0),
        ("UK", "social_static", VariantTheme.ugc, 1.8, 5.2, 1.3),
        ("NL", "social_static", VariantTheme.lifestyle, 1.6, 4.0, 1.1),
        ("NL", "paid_display", VariantTheme.product_only, 0.9, 2.1, 0.6),
        ("FR", "social_static", VariantTheme.lifestyle, 1.7, 4.4, 1.2),
        ("FR", "social_video", VariantTheme.ugc, 2.0, 6.1, 1.5),
        ("ES", "social_static", VariantTheme.promotional, 1.3, 3.3, 0.9),
        ("ES", "homepage_banner", VariantTheme.product_only, 0.8, 1.9, 0.5),
        ("UK", "social_video", VariantTheme.lifestyle, 2.2, 6.8, 1.6),
        ("NL", "social_video", VariantTheme.promotional, 1.5, 3.6, 1.0),
        ("FR", "paid_display", VariantTheme.product_only, 1.0, 2.4, 0.7),
        ("ES", "social_video", VariantTheme.ugc, 1.9, 5.5, 1.4),
    ]
    for i, (market, fmt, theme, ctr, eng, conv) in enumerate(other_rows):
        insights.append(CreativeInsight(
            brand=["Albelli", "Photobox", "Hofmann"][i % 3], market=market, format=fmt,
            variant_theme=theme, impressions=25000 + i * 2000, ctr=ctr,
            engagement_rate=eng, conversion_rate=conv,
            period_start=de_period_start, period_end=de_period_end,
            insight_text=None,
        ))
    session.add_all(insights)

    session.commit()


def reset():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def main():
    if "--reset" in sys.argv:
        reset()
        print("Database reset.")

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        if session.query(Person).count() > 0:
            print("Seed data already present — skipping (use --reset to start clean).")
            return
        seed(session)
        print("Seed data created: 8 people, 12 projects, 10 assignments, "
              "18 deliverables, 20 localisation rows, 24 creative insights.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
