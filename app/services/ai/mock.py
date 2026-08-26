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
    ResourceImpact,
    ResourceRecommendation,
    SuggestedWindow,
)

_MARKET_WORDS = {
    "nl": "NL", "netherlands": "NL", "dutch": "NL",
    "de": "DE", "germany": "DE", "german": "DE",
    "fr": "FR", "france": "FR", "french": "FR",
    "uk": "UK", "united kingdom": "UK", "britain": "UK",
    "es": "ES", "spain": "ES", "spanish": "ES",
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
_HEDGE_WORDS = ["ideally", "maybe", "probably", "not sure", "tbc", "tbd", "i think", "who signs off"]
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def mock_analyse_brief(raw_text: str) -> BriefExtraction:
    text = raw_text.lower()

    def word_in(word: str, haystack: str) -> bool:
        return re.search(rf"\b{re.escape(word)}\b", haystack) is not None

    markets = sorted({code for word, code in _MARKET_WORDS.items() if word_in(word, text)})

    matched_keywords = [kw for kw in _CHANNEL_KEYWORDS if word_in(kw, text)]
    channels = sorted({_CHANNEL_DELIVERABLE_MAP[kw][0] for kw in matched_keywords})
    deliverable_types = sorted({_CHANNEL_DELIVERABLE_MAP[kw][1] for kw in matched_keywords})

    hedged = any(h in text for h in _HEDGE_WORDS)
    weekday_mentioned = next((w for w in _WEEKDAYS if w in text), None)
    deadline = None
    ambiguities = []
    if weekday_mentioned and hedged:
        ambiguities.append(f"'{weekday_mentioned}' mentioned but not confirmed as a firm date")
    elif weekday_mentioned:
        deadline = f"next {weekday_mentioned}"

    owner_match = re.search(r"(?:approved|signed off) by (\w+)", raw_text, re.IGNORECASE)
    approval_owner = owner_match.group(1) if owner_match else None
    if approval_owner is None and ("who signs off" in text or "approval" not in text):
        ambiguities.append("no approval owner stated")

    audience_match = re.search(r"audience(?: is)?:?\s*([^.\n]+)", raw_text, re.IGNORECASE)
    audience = audience_match.group(1).strip() if audience_match else None
    if audience and any(h in audience.lower() for h in _HEDGE_WORDS):
        # A hedged audience statement ("...I think") is not a confirmed audience —
        # score it as missing, same treatment as a hedged deadline.
        ambiguities.append(f"audience stated but not confirmed: '{audience}'")
        audience = None

    format_match = re.search(r"(\d{3,4}x\d{3,4}|16:9)", raw_text)
    if not format_match and channels:
        ambiguities.append("no format specifications confirmed yet")

    sentences = [s.strip() for s in raw_text.split(".") if s.strip()]
    objective = sentences[0] if sentences else None

    deliverables = [
        DeliverableSpec(type=t, market=markets[0] if markets else None,
                       format_spec=format_match.group(1) if format_match else None, quantity=None)
        for t in deliverable_types
    ]

    localisation = LocalisationNeed(
        required=len(markets) > 1,
        source=markets[0] if markets else None,
        targets=markets[1:] if len(markets) > 1 else [],
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
    overloaded = conflict_facts["overloaded_person"]
    candidates = conflict_facts["candidates"]
    transfer_pct = conflict_facts["transfer_allocation_pct"]

    skill_matches = [c for c in candidates if c["matches_skill"]]
    pool = skill_matches or candidates
    chosen = max(pool, key=lambda c: c["available_pct"])

    from_new = overloaded["allocated_pct"] - transfer_pct
    to_new = chosen["allocated_pct"] + transfer_pct

    caveats = []
    if not chosen["matches_skill"]:
        caveats.append(f"{chosen['name']} does not have an exact skill match on record — verify fit before accepting.")
    if chosen.get("is_external"):
        caveats.append(f"{chosen['name']} is an external partner, not an internal team member.")

    confidence = "high" if chosen["matches_skill"] and to_new <= 100 else "medium"

    return ResourceRecommendation(
        action="reassign",
        project_id=conflict_facts["project_id"],
        from_person_id=overloaded["id"],
        to_person_id=chosen["id"],
        rationale=(
            f"{chosen['name']} holds a matching skill and has {chosen['available_pct']}% available. "
            f"Moving {conflict_facts['project_name']} from {overloaded['name']} to {chosen['name']} "
            f"drops {overloaded['name']} from {overloaded['allocated_pct']}% to {from_new}%, "
            f"protecting the {conflict_facts['deadline']} deadline."
        ),
        impact=ResourceImpact(
            from_person_new_allocation=from_new,
            to_person_new_allocation=to_new,
            deadline_protected=True,
        ),
        confidence=confidence,
        caveats=caveats,
    )


def mock_insight_to_action(insight_facts: dict, capacity_snapshot: list[dict]) -> ProductionRecommendation:
    market = insight_facts["market"]
    lifestyle_ctr = insight_facts["lifestyle_avg_ctr"]
    product_ctr = insight_facts["product_avg_ctr"]
    sample_size = insight_facts["sample_size"]

    pool = [c for c in capacity_snapshot if c["available_pct"] > 0]
    chosen = max(pool, key=lambda c: c["available_pct"]) if pool else None

    quantity = 3
    estimated_days = round(quantity * 0.7, 1)
    start = date.today() + timedelta(days=2)
    end = start + timedelta(days=int(estimated_days) or 1)

    caveats = []
    if sample_size < 10:
        caveats.append(f"Sample size is small (n={sample_size}); treat as directional.")

    localisation_required = market != "UK"

    return ProductionRecommendation(
        insight_summary=(
            f"Lifestyle-led creative is outperforming product-only creative in {market} "
            f"(CTR {lifestyle_ctr:.2f}% vs {product_ctr:.2f}%, n={sample_size} lifestyle variants)."
        ),
        recommended_action=f"Produce {quantity} additional lifestyle-led variants for {market}",
        deliverables=[
            ProductionDeliverable(type="social_static", market=market, quantity=quantity, format_spec="1080x1080"),
        ],
        estimated_days=estimated_days,
        suggested_person_id=chosen["id"] if chosen else capacity_snapshot[0]["id"],
        suggested_window=SuggestedWindow(start=start.isoformat(), end=end.isoformat()),
        localisation_required=localisation_required,
        localisation_note=f"{market} copy review required before publish" if localisation_required else None,
        confidence="medium" if sample_size < 10 else "high",
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
