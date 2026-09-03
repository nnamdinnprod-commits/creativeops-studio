"""REVIEW_03.md item 3's acceptance test — a real, realistically messy
multi-market brief that exercises every widened extraction path at once
(deadline formats, approval-owner phrasing, localisation deadline, 16
markets) and the original R5.1 bug (editing a brief and re-analysing must
actually move the score), driven through the real /brief routes end to end,
not just the mock function directly.
"""

from app.models import Person, PersonRole

SPRING_TOOLKIT_BRIEF = """\
SPRING TOOLKIT ROLLOUT — EUROPEAN MARKETS

Objective
Drive consideration for the spring personalisation range across all European markets with a single adaptable creative toolkit, replacing the current market-by-market approach.

Audience
Primary: existing customers aged 28–45 who purchased in the last 18 months. Secondary: lapsed customers, 24+ months. Segmentation confirmed for the five core markets; the smaller markets are still being defined by insights.

Markets
16 total. Core: NL, DE, FR, UK, ES.
Secondary: IT, BE, AT, CH, SE, DK, NO, FI, PL, PT, IE.
Master creative in English, adapted from there.

Deliverables per market
- Paid social statics: 6 per market, 1080x1080 and 1080x1350
- Paid social video: 3 per market, 9:16 and 1:1, 6s and 15s cuts
- Homepage banner set: 3 sizes, specs to be confirmed with web team
- Email header and two modules
- Display: standard IAB set

Motion specifications are not final — the web team are reviewing whether we move to a new banner framework before spring, which would change the homepage and display specs.

Timing
Campaign go-live 16 March, hard date, tied to the seasonal media buy.
Assets need to be with the media agency 10 working days before go-live.
Master creative approval targeted for mid-January, though that date has moved once already.

Dependencies
- Product photography for the new range is not yet shot; studio dates being discussed for early December
- Legal review required for the pricing claims in the email modules
- New brand guidelines land in November and apply to this work

Localisation
All 16 markets require copy adaptation, not straight translation. Core five need in-market review. Legal review required per market for the pricing claims. Master language decision — English or Dutch — not yet settled, which affects the adaptation route.

Approvals
Creative approval: Brand Director.
Final sign-off: not yet confirmed, likely European Marketing Director.

Budget
Approved in principle at last year's level plus 10%. Exact figure confirmed once the photography scope is settled.
"""


def _seed_producer(db_session):
    db_session.add(Person(name="Owner", role=PersonRole.producer, capacity_pct=100,
                          skills="", is_external=False))
    db_session.commit()


def test_spring_toolkit_brief_extracts_and_scores_correctly(client, db_session):
    _seed_producer(db_session)
    resp = client.post("/brief/analyse", data={"raw_text": SPRING_TOOLKIT_BRIEF})
    assert resp.status_code == 200
    html = resp.text

    # All 16 markets, not just the 5 described as core -- rendered as one
    # sorted, comma-joined line in the Extracted fields panel.
    all_16 = ["NL", "DE", "FR", "UK", "ES", "IT", "BE", "AT", "CH",
             "SE", "DK", "NO", "FI", "PL", "PT", "IE"]
    assert ", ".join(sorted(all_16)) in html

    # 16 March recognised as a hard, confirmed date (not "Not confirmed").
    assert "Not confirmed" not in html.split("Deadline")[1][:200]

    # The score lands in the 70s-to-low-80s band the review asked for.
    import re
    score_match = re.search(r'font-semibold[^>]*>(\d+)%', html)
    assert score_match is not None, "readiness score not found on the page"
    score = int(score_match.group(1))
    assert 70 <= score <= 84, f"expected score in the 70s/low 80s band, got {score}"

    # Missing/blocking items the review named.
    assert "format" in html.lower() and "Missing" in html
    assert "approval_owner" in html or "Approval owner" in html

    # Ambiguities the review named, even though they don't move the score.
    assert "language" in html.lower()
    assert "photography" in html.lower()


def test_editing_the_brief_and_re_analysing_moves_the_score(client, db_session):
    """The original reported bug (REVIEW_03.md R5.1): adding an approval owner
    and a localisation deadline to an edited brief must produce a different
    score, not the original one repeated."""
    _seed_producer(db_session)
    first = client.post("/brief/analyse", data={"raw_text": SPRING_TOOLKIT_BRIEF})
    import re
    first_score = int(re.search(r'font-semibold[^>]*>(\d+)%', first.text).group(1))

    edited = SPRING_TOOLKIT_BRIEF.replace(
        "Final sign-off: not yet confirmed, likely European Marketing Director.",
        "Final sign-off: Jane Doe.",
    ).replace(
        "Master language decision — English or Dutch — not yet settled, which affects the adaptation route.",
        "Master language decision — English or Dutch — not yet settled, which affects the adaptation route. "
        "Localisation deadline: 20 February.",
    )
    second = client.post("/brief/analyse", data={"raw_text": edited})
    assert second.status_code == 200
    second_score = int(re.search(r'font-semibold[^>]*>(\d+)%', second.text).group(1))

    assert second_score > first_score, (
        f"editing the brief to add an approval owner should raise the score "
        f"(was {first_score}, still {second_score})"
    )
    assert "Jane Doe" in second.text
