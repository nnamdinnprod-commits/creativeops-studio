"""Deterministic creative-performance comparisons. Python computes the CTR gap;
app/services/ai/insight.py only turns an already-computed gap into a production
recommendation. See AI_WORKFLOWS.md's governing rule — numbers are never the
model's to produce.
"""

import json
from collections import defaultdict
from statistics import mean

from sqlalchemy.orm import Session

from app.models import CreativeInsight, Recommendation, RecommendationKind, RecommendationStatus, VariantTheme

# Lifestyle CTR must exceed product-only CTR by at least this many percentage
# points, in the same market, to be worth surfacing as an actionable gap.
GAP_THRESHOLD_PCT = 0.5


def compute_market_comparisons(insights: list[CreativeInsight]) -> list[dict]:
    groups: dict[tuple[str, VariantTheme], list[CreativeInsight]] = defaultdict(list)
    for row in insights:
        groups[(row.market, row.variant_theme)].append(row)

    markets = sorted({market for market, _ in groups})
    comparisons = []
    for market in markets:
        lifestyle = groups.get((market, VariantTheme.lifestyle), [])
        product = groups.get((market, VariantTheme.product_only), [])
        if not lifestyle or not product:
            continue

        lifestyle_ctr = round(mean(row.ctr for row in lifestyle), 2)
        product_ctr = round(mean(row.ctr for row in product), 2)
        gap = round(lifestyle_ctr - product_ctr, 2)
        if gap < GAP_THRESHOLD_PCT:
            continue

        comparisons.append({
            "market": market,
            "lifestyle_avg_ctr": lifestyle_ctr,
            "product_avg_ctr": product_ctr,
            "gap": gap,
            # The recommendation extrapolates from the lifestyle group specifically
            # (matches AI_WORKFLOWS.md's "n=6" convention) — this is what should
            # drive the "small sample, treat as directional" caveat, not the
            # combined count, which reads as artificially larger than it is.
            "sample_size": len(lifestyle),
            "lifestyle_count": len(lifestyle),
            "product_count": len(product),
        })

    return sorted(comparisons, key=lambda c: c["gap"], reverse=True)


def _insight_rows_for_market(db: Session, market: str) -> list[CreativeInsight]:
    return (
        db.query(CreativeInsight)
        .filter(CreativeInsight.market == market,
               CreativeInsight.variant_theme.in_([VariantTheme.lifestyle, VariantTheme.product_only]))
        .all()
    )


def compute_insight_status(db: Session, market: str) -> dict:
    """REVIEW_02.md P4: one lifecycle per market opportunity. `recommendation_pending`
    and `actioned` are derived from Recommendation rows, never stored — only
    `dismissed` has no other source of truth, so it's the one thing read off the
    CreativeInsight rows themselves. Mirrors resources.py's own "one pending per
    conflict" pattern, generalised to this screen (REVIEW_02.md P4's stated gap:
    the round 1 fix reached Resources but not Creative Intelligence)."""
    rows = _insight_rows_for_market(db, market)
    if rows and any(r.dismissed_reason for r in rows):
        return {"status": "dismissed", "dismissed_reason": next(r.dismissed_reason for r in rows if r.dismissed_reason)}

    production_recs = db.query(Recommendation).filter_by(kind=RecommendationKind.production_action).all()
    matching = [r for r in production_recs if json.loads(r.computed_facts_json).get("market") == market]

    accepted = next((r for r in matching if r.status == RecommendationStatus.accepted), None)
    if accepted is not None:
        return {"status": "actioned", "outcome_note": accepted.outcome_note, "project_id": accepted.project_id}

    pending = next((r for r in matching if r.status == RecommendationStatus.pending), None)
    if pending is not None:
        return {"status": "recommendation_pending", "recommendation_id": pending.id}

    return {"status": "new"}


def dismiss_market_insight(db: Session, market: str, reason: str) -> bool:
    rows = _insight_rows_for_market(db, market)
    if not rows:
        return False
    for row in rows:
        row.dismissed_reason = reason
    db.commit()
    return True
