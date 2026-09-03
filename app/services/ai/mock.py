"""Mock implementation of every AI function, matching the real functions' shapes
exactly. The app must run fully with no API key set — see docs/AI_WORKFLOWS.md.

These are not random placeholders: each one reads the deterministic facts it is
given (the same facts a live model would receive) and builds a response from
them, so the demo stays coherent with whatever seed data is on screen.
"""

import re
from datetime import date, datetime, timedelta

from app.services.ai.schemas import (
    AttentionBrief,
    AttentionItem,
    BriefExtraction,
    DeliverableSpec,
    LocalisationNeed,
    LocalisationRisk,
    ProductionDeliverable,
    ProductionRecommendation,
    QuickEstimate,
    QuickEstimateAssumption,
    ResourceOption,
    ResourceRecommendation,
    ScheduleAssessment,
    ScheduleOption,
    SuggestedWindow,
)

# REVIEW_03.md item 3: was 5 markets, matched by lowercasing the whole brief and
# checking 2-letter codes as plain words — fine for nl/de/fr/uk/es, but several
# of the other 11 markets a real European rollout brief names are common English
# words as bare lowercase tokens (it/be/at/no/ie). _MARKET_CODES below is
# matched case-SENSITIVELY against the original text instead, since a genuine
# market-code mention is written in caps ("...core markets. Secondary: IT, BE,
# AT...") and English prose essentially never capitals-only spells "IT"/"NO"/
# "IE" as a whole word. Full country names stay case-insensitive — no ambiguity
# there.
_MARKET_CODES = ["NL", "DE", "FR", "UK", "ES", "IT", "BE", "AT", "CH",
                 "SE", "DK", "NO", "FI", "PL", "PT", "IE"]
_MARKET_FULL_NAMES = {
    "netherlands": "NL", "dutch": "NL",
    "germany": "DE", "german": "DE",
    "france": "FR", "french": "FR",
    "united kingdom": "UK", "britain": "UK",
    "spain": "ES", "spanish": "ES",
    "italy": "IT", "italian": "IT",
    "belgium": "BE", "belgian": "BE",
    "austria": "AT", "austrian": "AT",
    "switzerland": "CH", "swiss": "CH",
    "sweden": "SE", "swedish": "SE",
    "denmark": "DK", "danish": "DK",
    "norway": "NO", "norwegian": "NO",
    "finland": "FI", "finnish": "FI",
    "poland": "PL", "polish": "PL",
    "portugal": "PT", "portuguese": "PT",
    "ireland": "IE", "irish": "IE",
}
_CHANNEL_KEYWORDS = ["social", "homepage", "email", "display", "video"]

# (channel tag, deliverable type) — two different vocabularies per
# AI_WORKFLOWS.md's own example: channels are marketing-channel tags,
# deliverables[].type must match the DeliverableType enum exactly.
_CHANNEL_DELIVERABLE_MAP = {
    "video": ("paid_social", "social_video"),
    "social": ("paid_social", "social_static"),
    "homepage": ("homepage", "homepage_banner"),
    "email": ("email", "email"),
    "display": ("paid_display", "paid_display"),
}
# REVIEW_03.md item 3: widened from the original 8 — a professionally-written
# brief hedges in plain business language ("not yet confirmed", "still being
# discussed"), not just casual ones ("maybe", "I think").
_HEDGE_WORDS = [
    "ideally", "maybe", "probably", "not sure", "tbc", "tbd", "i think",
    "who signs off", "likely", "not yet", "not confirmed", "not settled",
    "not final", "still being", "being discussed", "moved once already",
    "to be confirmed",
]
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_MONTHS = ["january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december"]
_MONTH_PATTERN = "|".join(m.capitalize() for m in _MONTHS)
_WEEKDAY_PATTERN = "|".join(w.capitalize() for w in _WEEKDAYS)

# REVIEW_03.md item 3: deadline extraction used to recognise a weekday name and
# nothing else. Real briefs state dates several ways — this covers ISO, "16
# March" / "March 16", DD/MM(/YYYY), and the weekday case, each as a named
# group so _resolve_date_match can dispatch on whichever one fired.
_DATE_PATTERN = re.compile(
    rf"(?P<iso>\b\d{{4}}-\d{{2}}-\d{{2}}\b)"
    rf"|(?P<day_month>\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTH_PATTERN})\b)"
    rf"|(?P<month_day>\b(?:{_MONTH_PATTERN})\s+\d{{1,2}}(?:st|nd|rd|th)?\b)"
    rf"|(?P<dmy>\b\d{{1,2}}/\d{{1,2}}(?:/\d{{2,4}})?\b)"
    rf"|(?P<weekday>\b(?:{_WEEKDAY_PATTERN})\b)",
    re.IGNORECASE,
)

# Vague timing that names no resolvable date — REVIEW_03.md item 3 asks that
# these be captured as a stated target window rather than silently discarded,
# not resolved into a fake firm date.
_VAGUE_MONTH_PATTERN = re.compile(rf"\b(?:early|mid|late)[- ](?:{_MONTH_PATTERN})\b", re.IGNORECASE)
_VAGUE_SEASON_PATTERN = re.compile(
    r"\b(?:spring|summer|autumn|fall|winter)\s+(?:next year|this year|\d{4})\b", re.IGNORECASE)
_VAGUE_RELATIVE_PATTERN = re.compile(r"\bend of (?:next|this) week\b", re.IGNORECASE)

_APPROVAL_OWNER_PATTERNS = [
    r"approved by ([^.,\n]+)",
    r"signed off by ([^.,\n]+)",
    r"sign-?off:?\s*([^.\n]+)",
    r"final approval sits with ([^.\n]+)",
    r"approval owner:?\s*([^.\n]+)",
    r"owner:?\s*([^.\n]+)",
    r"([A-Z][\w' ]*?)\s+to approve\b",
]

_LOCALISATION_DEADLINE_PATTERNS = [
    r"localisation deadline:?\s*([^.\n]+)",
    r"localization deadline:?\s*([^.\n]+)",
    r"translations?\s+(?:due|deadline)\s*:?\s*([^.\n]+)",
    r"localised?\s+assets?\s+(?:due|by)\s+([^.\n]+)",
]
# A lead time stated before the main deadline ("assets need to be with the
# agency N working days before go-live") is a real localisation-relevant fact
# even though it never says the words "localisation deadline" — resolved
# against the confirmed deadline once one is known, into an actual date.
_LEAD_TIME_BEFORE_DEADLINE_PATTERN = re.compile(
    r"(?:assets?|deliverables?|creative)[^.\n]*?(?:with|to)\s+(?:the\s+)?(?:media\s+)?agency\s+"
    r"(\d+)\s+working days?\s+before",
    re.IGNORECASE,
)


def _clause_span_around(text: str, start: int, end: int) -> tuple[int, int]:
    """Start/end of the sentence/line containing a match — a hedge word
    elsewhere in a long, multi-section brief shouldn't suppress confidence in
    an unrelated, clearly stated fact (REVIEW_03.md item 3's whole reason for
    existing: the original hedge check was global across the entire brief)."""
    boundary_chars = (".", "\n", ";")
    left = max((text.rfind(c, 0, start) for c in boundary_chars), default=-1)
    right_candidates = [i for i in (text.find(c, end) for c in boundary_chars) if i != -1]
    right = min(right_candidates) if right_candidates else len(text)
    return left + 1, right


def _clause_around(text: str, start: int, end: int) -> str:
    left, right = _clause_span_around(text, start, end)
    return text[left:right]


def _spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _is_hedged(clause: str) -> bool:
    lowered = clause.lower()
    return any(h in lowered for h in _HEDGE_WORDS)


def _next_month_day(today: date, month: int, day: int) -> date | None:
    """Nearest occurrence of month/day that isn't in the past — same "next
    occurrence" logic the existing weekday handling already used, extended to
    a full calendar date."""
    try:
        candidate = date(today.year, month, day)
    except ValueError:
        return None
    if candidate < today:
        try:
            candidate = date(today.year + 1, month, day)
        except ValueError:
            return None
    return candidate


def _resolve_date_match(match: re.Match, today: date) -> date | None:
    if match.group("iso"):
        try:
            return date.fromisoformat(match.group("iso"))
        except ValueError:
            return None
    if match.group("day_month"):
        day_str, month_str = re.match(r"(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)", match.group("day_month")).groups()
        return _next_month_day(today, _MONTHS.index(month_str.lower()) + 1, int(day_str))
    if match.group("month_day"):
        month_str, day_str = re.match(r"(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?", match.group("month_day")).groups()
        return _next_month_day(today, _MONTHS.index(month_str.lower()) + 1, int(day_str))
    if match.group("dmy"):
        parts = match.group("dmy").split("/")
        day, month = int(parts[0]), int(parts[1])
        if len(parts) == 3:
            year = int(parts[2])
            if year < 100:
                year += 2000
            try:
                return date(year, month, day)
            except ValueError:
                return None
        return _next_month_day(today, month, day)
    if match.group("weekday"):
        target_idx = _WEEKDAYS.index(match.group("weekday").lower())
        days_ahead = (target_idx - today.weekday()) % 7 or 7
        return today + timedelta(days=days_ahead)
    return None


def _working_days_before_iso(deadline_iso: str, working_days: int) -> str:
    current = date.fromisoformat(deadline_iso)
    remaining = working_days
    while remaining > 0:
        current -= timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current.isoformat()


def _extract_markets(raw_text: str) -> list[str]:
    lowered = raw_text.lower()
    found = {code for code in _MARKET_CODES if re.search(rf"\b{code}\b", raw_text)}
    found |= {code for name, code in _MARKET_FULL_NAMES.items()
             if re.search(rf"\b{re.escape(name)}\b", lowered)}
    return sorted(found)

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "a dozen": 12, "twenty": 20,
}
# Checked in this order — "event"/"film" keywords are unambiguous; "shoot" alone is not
# (it also drives the original_photography toggle), so it's deliberately not a work_type
# signal on its own.
_WORK_TYPE_KEYWORDS = [
    ("event", ["event", "activation", "fabrication", "live show"]),
    ("film", ["film", "video", "commercial", "branded content"]),
    ("stills", ["photo", "photography", "lookbook", "catalogue"]),
    ("social", ["social", "campaign", "ai-generated", "ai generated"]),
]


def mock_analyse_brief(raw_text: str) -> BriefExtraction:
    text = raw_text.lower()
    today = date.today()
    ambiguities: list[str] = []

    def word_in(word: str, haystack: str) -> bool:
        return re.search(rf"\b{re.escape(word)}\b", haystack) is not None

    markets = _extract_markets(raw_text)
    matched_keywords = [kw for kw in _CHANNEL_KEYWORDS if word_in(kw, text)]
    channels = sorted({_CHANNEL_DELIVERABLE_MAP[kw][0] for kw in matched_keywords})

    # REVIEW_03.md item 3: deadline extraction — was weekday-only, hedge-checked
    # against the *entire* brief. Now scans every recognised date format and
    # takes the first one whose own sentence isn't hedged, in reading order —
    # "16 March, hard date" wins over a vague "mid-January" mentioned for a
    # different milestone elsewhere, and an unrelated hedge word two sections
    # away no longer suppresses a clearly-stated date.
    # Spans already turned into a specific ambiguity or extracted fact below —
    # the generic hedge-sentence pass at the end skips any clause overlapping
    # one of these, so the same underlying statement is never reported twice.
    consumed_spans: list[tuple[int, int]] = []

    deadline = None
    hedged_date_mentions: list[str] = []
    for match in _DATE_PATTERN.finditer(raw_text):
        resolved = _resolve_date_match(match, today)
        if resolved is None:
            continue
        clause_span = _clause_span_around(raw_text, *match.span())
        if _is_hedged(raw_text[clause_span[0]:clause_span[1]]):
            hedged_date_mentions.append(match.group(0))
            consumed_spans.append(clause_span)
            continue
        deadline = resolved.isoformat()
        break
    if deadline is None and hedged_date_mentions:
        ambiguities.append(
            f"'{hedged_date_mentions[0]}' mentioned but not confirmed as a firm date")

    # Vague windows ("mid-January", "spring next year", "end of next week") name
    # no resolvable date at all — captured as a stated target window rather
    # than silently discarded, regardless of whether a firm deadline was found
    # elsewhere in the brief.
    for pattern in (_VAGUE_MONTH_PATTERN, _VAGUE_SEASON_PATTERN, _VAGUE_RELATIVE_PATTERN):
        for match in pattern.finditer(raw_text):
            consumed_spans.append(_clause_span_around(raw_text, *match.span()))
            ambiguities.append(f"vague target window mentioned: '{match.group(0)}' — no confirmed date")

    # REVIEW_03.md item 3: approval owner — was one exact regex ("approved by
    # X" / "signed off by X"). Several phrasings now, each hedge-checked on its
    # own captured clause — "Final sign-off: not yet confirmed, likely X" must
    # not be read as a confirmed owner just because a name appears in it.
    approval_owner = None
    owner_unconfirmed_clause = None
    for pattern in _APPROVAL_OWNER_PATTERNS:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(1).strip().rstrip(".,")
        consumed_spans.append(_clause_span_around(raw_text, *match.span()))
        if _is_hedged(candidate):
            owner_unconfirmed_clause = candidate
        else:
            approval_owner = candidate
        break
    if approval_owner is None:
        if owner_unconfirmed_clause:
            ambiguities.append(f"approval owner not yet confirmed ({owner_unconfirmed_clause})")
        elif "who signs off" in text or "approval" not in text:
            ambiguities.append("no approval owner stated")

    audience_match = re.search(r"audience(?: is)?:?\s*([^.\n]+)", raw_text, re.IGNORECASE)
    audience = audience_match.group(1).strip() if audience_match else None
    if audience and _is_hedged(audience):
        # A hedged audience statement ("...I think") is not a confirmed audience —
        # score it as missing, same treatment as a hedged deadline.
        ambiguities.append(f"audience stated but not confirmed: '{audience}'")
        audience = None

    # REVIEW_03.md item 3: format specs are now checked per deliverable type,
    # in that type's own clause — a brief can confirm specs for one channel and
    # leave another's "to be confirmed", and the difference matters (a producer
    # can scope paid social today but not the homepage banner).
    deliverables = []
    for kw in matched_keywords:
        channel, dtype = _CHANNEL_DELIVERABLE_MAP[kw]
        kw_match = re.search(rf"\b{re.escape(kw)}\b", raw_text, re.IGNORECASE)
        if kw_match:
            clause_span = _clause_span_around(raw_text, *kw_match.span())
            clause = raw_text[clause_span[0]:clause_span[1]]
            consumed_spans.append(clause_span)
        else:
            clause = ""
        format_match = re.search(r"\d{3,4}x\d{3,4}|16:9|9:16|1:1", clause)
        format_spec = format_match.group(0) if format_match else None
        if format_spec is None:
            ambiguities.append(f"{dtype.replace('_', ' ')} format specs not yet confirmed")
        deliverables.append(DeliverableSpec(
            type=dtype, market=markets[0] if markets else None, format_spec=format_spec, quantity=None))

    # REVIEW_03.md item 3: localisation deadline — a real extracted fact now,
    # not a proxy off the main deadline (see app/services/brief.py). Checked as
    # its own set of phrasings first; a lead time stated before the main
    # deadline ("assets need to be with the agency N working days before
    # go-live") is the fallback, resolved into an actual date once the main
    # deadline is known.
    localisation_deadline = None
    for pattern in _LOCALISATION_DEADLINE_PATTERNS:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip().rstrip(".,")
            if not _is_hedged(candidate):
                localisation_deadline = candidate
            break
    if localisation_deadline is None and deadline is not None:
        lead_match = _LEAD_TIME_BEFORE_DEADLINE_PATTERN.search(raw_text)
        if lead_match:
            localisation_deadline = _working_days_before_iso(deadline, int(lead_match.group(1)))

    # REVIEW_03.md item 3: a generic pass for sentences that hedge on something
    # this mock has no dedicated field for (a language decision, an unbooked
    # dependency) — real information a producer needs to see, not something to
    # drop just because there's no rubric column for it. Skips clauses already
    # surfaced by a more specific check above, so nothing is reported twice.
    _GENERIC_EXCLUDE = ("sign-off", "signed off", "approved by", "approval owner", "who signs off")
    cursor = 0
    for raw_clause in re.split(r"([.\n;])", raw_text):
        clause_start = raw_text.index(raw_clause, cursor) if raw_clause else cursor
        cursor = clause_start + len(raw_clause)
        clause = raw_clause.strip().lstrip("-•*").strip()
        if len(clause) < 8 or not _is_hedged(clause):
            continue
        lowered_clause = clause.lower()
        if any(k in lowered_clause for k in _GENERIC_EXCLUDE):
            continue
        clause_span = (clause_start, clause_start + len(raw_clause))
        if any(_spans_overlap(clause_span, consumed) for consumed in consumed_spans):
            continue
        ambiguities.append(clause)

    sentences = [s.strip() for s in raw_text.split(".") if s.strip()]
    objective = sentences[0] if sentences else None

    localisation = LocalisationNeed(
        required=len(markets) > 1,
        source=markets[0] if markets else None,
        targets=markets[1:] if len(markets) > 1 else [],
        deadline=localisation_deadline,
    )

    return BriefExtraction(
        objective=objective,
        audience=audience,
        markets=markets,
        channels=channels,
        deliverables=deliverables,
        deadline=deadline,
        dependencies=[],
        resource_needs=["designer"] if channels else [],
        localisation=localisation,
        approval_owner=approval_owner,
        ambiguities=ambiguities,
    )


def mock_recommend_resource(conflict_facts: dict) -> ResourceRecommendation:
    """REVIEW_02.md P5.6: picks among Python-computed options (reassign / engage
    external / move delivery) rather than producing the single action itself —
    every number in the chosen option already came from conflict_facts, computed
    before this function ever runs (resources.py's _build_conflict_facts)."""
    overloaded = conflict_facts["overloaded_person"]
    options = [ResourceOption(**opt) for opt in conflict_facts["options"]]

    # Cheapest, fastest first: an internal reassignment costs nothing and needs no
    # notice, so it's preferred whenever one exists; external engagement is the
    # next-best real alternative; moving delivery is the last resort — it doesn't
    # resolve the conflict itself, it needs a client conversation first.
    _KIND_PRIORITY = {"reassign": 0, "engage_external": 1, "move_delivery": 2}
    recommended = min(options, key=lambda o: _KIND_PRIORITY[o.kind])

    # Built from recommended.action/detail directly rather than parsed out of
    # them — both are already complete, Python-computed clauses (e.g. "Reassign
    # to Maya"), so quoting them whole avoids any string-splitting assumption
    # about their exact wording.
    caveats = []
    if recommended.kind == "move_delivery":
        rationale = (
            "No internal or external candidate can take this on in time — the deadline "
            "itself is the only lever left, and that needs a client conversation, not a "
            "Python decision."
        )
        caveats.append("Confirm the new date with the client before treating this as resolved.")
    elif recommended.kind == "engage_external":
        rationale = (
            f"No one on the Team has spare capacity for this. {recommended.action} from "
            f"the talent pool covers it at a real but bounded cost."
        )
        caveats.append("This candidate is an external partner, not an internal team member.")
    else:
        # REVIEW_03.md R2.4: quotes recommended.detail whole, which now carries
        # the headroom comparison resources.py computed ("55% free, against
        # Nadia's 50%") whenever a genuine runner-up exists — "say so in the
        # rationale" without this function inventing or re-deriving the numbers.
        rationale = (
            f"{recommended.action} — {recommended.detail}, the fastest no-cost way to "
            f"bring {overloaded['name']} back under {overloaded['capacity_pct']}%."
        )

    return ResourceRecommendation(
        project_id=conflict_facts["project_id"],
        options=options,
        recommended_label=recommended.label,
        rationale=rationale,
        confidence="high" if recommended.kind == "reassign" else "medium",
        caveats=caveats,
    )


# Matches app/services/insight.py's MIN_SAMPLE_SIZE conceptually (below this
# many rows, a group is thin) — not imported from there since that constant
# gates a different question (is the *market* significant enough to
# recommend for at all); this one only decides whether the brand-specific
# narration needs a directional caveat.
_MIN_BRAND_SAMPLE_SIZE = 3


def mock_insight_to_action(insight_facts: dict, capacity_snapshot: list[dict]) -> ProductionRecommendation:
    """REVIEW_03.md R10: used to read only market/lifestyle_avg_ctr/
    product_avg_ctr/sample_size — all market-wide, brand-blind figures — so
    every brand selection for the same market produced identical output.
    `brand_breakdown` (app/services/insight.py's compute_brand_breakdown) is
    that same brand's own CTR figures from the same underlying rows, computed
    separately from the market-wide comparison that decides whether this
    market is significant enough to recommend for at all — that gate has to
    stay market-wide to keep its sample size meaningful, but the narration
    itself should reflect whichever brand was actually picked, not the whole
    market pooled together."""
    market = insight_facts["market"]
    brand = insight_facts.get("brand")
    breakdown = insight_facts.get("brand_breakdown")

    if breakdown is not None:
        lifestyle_ctr = breakdown["lifestyle_avg_ctr"]
        product_ctr = breakdown["product_avg_ctr"]
        sample_size = breakdown["lifestyle_count"]
        scope = f"{brand} in {market}"
    else:
        lifestyle_ctr = insight_facts["lifestyle_avg_ctr"]
        product_ctr = insight_facts["product_avg_ctr"]
        sample_size = insight_facts["sample_size"]
        scope = market

    pool = [c for c in capacity_snapshot if c["available_pct"] > 0]
    chosen = max(pool, key=lambda c: c["available_pct"]) if pool else None

    quantity = 3
    estimated_days = round(quantity * 0.7, 1)
    start = date.today() + timedelta(days=2)
    end = start + timedelta(days=int(estimated_days) or 1)

    caveats = []
    if breakdown is not None and sample_size < _MIN_BRAND_SAMPLE_SIZE:
        caveats.append(
            f"Based on {brand}'s own {sample_size} lifestyle variants in {market}, "
            f"not the full market sample; treat as directional."
        )
    elif breakdown is None and brand:
        caveats.append(f"No {brand}-specific data yet — this reflects {market} as a whole.")
    elif sample_size < 10:
        caveats.append(f"Sample size is small (n={sample_size}); treat as directional.")

    localisation_required = market != "UK"

    return ProductionRecommendation(
        insight_summary=(
            f"Lifestyle-led creative is outperforming product-only creative for {scope} "
            f"(CTR {lifestyle_ctr:.2f}% vs {product_ctr:.2f}%, n={sample_size} lifestyle variants)."
        ),
        recommended_action=(
            f"Produce {quantity} additional {brand + ' ' if brand else ''}lifestyle-led variants for {market}"
        ),
        deliverables=[
            ProductionDeliverable(type="social_static", market=market, quantity=quantity, format_spec="1080x1080"),
        ],
        estimated_days=estimated_days,
        suggested_person_id=chosen["id"] if chosen else capacity_snapshot[0]["id"],
        suggested_window=SuggestedWindow(start=start.isoformat(), end=end.isoformat()),
        localisation_required=localisation_required,
        localisation_note=f"{market} copy review required before publish" if localisation_required else None,
        confidence="low" if (breakdown is not None and sample_size < _MIN_BRAND_SAMPLE_SIZE) else (
            "medium" if sample_size < 10 else "high"),
        caveats=caveats,
    )


_CAUSE_PHRASING = {
    "capacity": "{name} is at risk — {detail}",
    "localisation": "{name} is blocked — {detail}",
    "brief": "{name} cannot safely enter production — {detail}",
    "deadline": "{name} is running out of runway — {detail}",
}


def mock_assess_portfolio_attention(snapshot: list[dict]) -> AttentionBrief:
    if not snapshot:
        return AttentionBrief(headline="No projects need intervention this week.", items=[])

    items = [
        AttentionItem(
            project_id=entry["project_id"],
            severity=entry["severity"],
            cause=entry["cause"],
            statement=_CAUSE_PHRASING.get(entry["cause"], "{name} — {detail}").format(
                name=entry["project_name"], detail=entry["detail"]
            ),
            suggested_screen=entry["suggested_screen"],
        )
        for entry in snapshot
    ]
    return AttentionBrief(
        headline=f"{len(items)} project{'s' if len(items) != 1 else ''} need intervention this week",
        items=items,
    )


def mock_check_localisation_risk(project_localisation_facts: dict) -> LocalisationRisk:
    """Operates at the project level — a project can have several target markets,
    and Python (app/services/localisation_risk.py) has already decided which of
    them are at risk and why. This function only composes the phrasing."""
    at_risk = project_localisation_facts["at_risk"]
    at_risk_markets = project_localisation_facts.get("at_risk_markets", [])
    reasons = project_localisation_facts.get("reasons", [])
    min_days_to_due = project_localisation_facts.get("min_days_to_due")

    if not at_risk:
        return LocalisationRisk(
            at_risk=False,
            markets_at_risk=[],
            reason="No localisation risk detected for this project.",
            suggested_action="No action needed.",
            severity="low",
        )

    reason = " ".join(reasons) if reasons else f"{', '.join(at_risk_markets)} localisation is at risk."
    suggested_action = (
        f"Assign a translator or resolve the review stall for "
        f"{', '.join(at_risk_markets)} before it slips further."
    )
    severity = "high" if min_days_to_due is not None and min_days_to_due <= 4 else "medium"

    return LocalisationRisk(
        at_risk=True,
        markets_at_risk=at_risk_markets,
        reason=reason,
        suggested_action=suggested_action,
        severity=severity,
    )


def mock_assess_schedule_feasibility(computed_schedule_facts: dict) -> ScheduleAssessment:
    if computed_schedule_facts.get("feasible", True):
        return ScheduleAssessment(
            feasible=True, shortfall_days=0, binding_constraint=None,
            statement="This schedule fits comfortably within the deadline.",
            options=[], confidence="high", caveats=[],
        )

    shortfall = computed_schedule_facts["shortfall_days"]
    project_start = computed_schedule_facts["project_start"]
    candidates = computed_schedule_facts.get("binding_constraint_candidates", [])
    top = candidates[0] if candidates else None

    statement = (
        f"Working backwards from the deadline, this project needed to start {project_start} "
        f"— {shortfall} working day{'s' if shortfall != 1 else ''} ago."
    )
    if top is not None:
        statement += (
            f" {top['phase_name']} ({top['working_days']} working days) is the largest "
            "single contributor."
        )

    return ScheduleAssessment(
        feasible=False,
        shortfall_days=shortfall,
        binding_constraint=top["phase_name"] if top else None,
        statement=statement,
        options=[ScheduleOption(**opt) for opt in computed_schedule_facts.get("options", [])],
        confidence="high",
        caveats=[],
    )


def _infer_work_type(text: str) -> str:
    for work_type, keywords in _WORK_TYPE_KEYWORDS:
        if any(kw in text for kw in keywords):
            return work_type
    return "social"  # BRIEF_MODES.md's own worked example — the most common minimal ask


_VOLUME_HEDGE_WORDS = ["or so", "roughly", "about", "around", "ish"]


def _infer_asset_count(text: str) -> tuple[int, str]:
    # A hedged number ("six or so assets") is a stated ballpark, not a confirmed count —
    # BRIEF_MODES.md's own example treats it as assumed, not inferred.
    source = "assumed" if any(h in text for h in _VOLUME_HEDGE_WORDS) else "inferred"
    digit_match = re.search(r"(\d+)\s*(?:assets?|statics?|variants?|deliverables?)", text)
    if digit_match:
        return int(digit_match.group(1)), source
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", text):
            return value, source
    return 6, "assumed"


def _infer_original_photography(text: str) -> tuple[bool, str]:
    if re.search(r"no\s+(?:original\s+)?(?:shoot|photography|photo shoot)", text):
        return False, "inferred"
    if "shoot" in text or "photography" in text:
        return True, "inferred"
    return False, "assumed"


def mock_quick_estimate(raw_text: str) -> QuickEstimate:
    text = raw_text.lower()

    work_type = _infer_work_type(text)
    asset_count, volume_confidence = _infer_asset_count(text)
    original_photography, photography_source = _infer_original_photography(text)
    markets = _extract_markets(raw_text)
    localisation_required = len(markets) > 0

    review_rounds = 2  # ASSUMPTIONS.md's default_review_rounds — mocks don't read the DB
    review_match = re.search(r"(\d+)\s*(?:client\s*)?review", text)
    review_source = "default"
    if review_match:
        review_rounds = int(review_match.group(1))
        review_source = "inferred"

    assumptions = [
        QuickEstimateAssumption(key="asset_count", value=asset_count, source=volume_confidence),
        QuickEstimateAssumption(key="original_photography", value=original_photography,
                                source=photography_source),
        QuickEstimateAssumption(key="review_rounds", value=review_rounds, source=review_source),
    ]

    inferred_count = sum(1 for a in assumptions if a.source == "inferred") + (1 if markets else 0)
    if inferred_count >= 4:
        confidence = "high"
    elif inferred_count >= 2:
        confidence = "medium"
    elif inferred_count >= 1:
        confidence = "low_medium"
    else:
        confidence = "low"

    if volume_confidence != "inferred":
        single_best_question = "How many assets, and are they all static?"
    elif not markets:
        single_best_question = "Which market is this for?"
    elif photography_source != "inferred":
        single_best_question = "Is any original photography or filming needed, or is this working from existing assets?"
    else:
        single_best_question = "Is there a target delivery date, or is 'as soon as possible' the real constraint?"

    caveats = ["No deadline given; earliest delivery is calculated from today."]
    if volume_confidence == "assumed":
        caveats.append(f"Asset count assumed at {asset_count} — confirming it would narrow the range.")

    return QuickEstimate(
        work_type=work_type,
        inferred_volume=asset_count,
        volume_confidence=volume_confidence,
        markets=markets,
        localisation_required=localisation_required,
        assumptions=assumptions,
        single_best_question=single_best_question,
        confidence=confidence,
        caveats=caveats,
    )
