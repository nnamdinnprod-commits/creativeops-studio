"""Deterministic creative-performance comparisons. Python computes the CTR gap;
app/services/ai/insight.py only turns an already-computed gap into a production
recommendation. See AI_WORKFLOWS.md's governing rule — numbers are never the
model's to produce.
"""

from collections import defaultdict
from statistics import mean

from app.models import CreativeInsight, VariantTheme

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
