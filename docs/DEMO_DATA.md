# Demo Data Specification

All data here is invented. See `docs/POSITIONING.md` for the rules this must obey.

The seed data has one job: make the demo's arguments visible without the presenter having
to set anything up. Every conflict below exists because a specific screen needs to show it.

## Scale

Small enough to read on one screen, large enough to be believable: **3 brands, 5 markets,
13 people, 12 projects, ~30 deliverables, ~20 localisation rows, ~24 creative insight rows.**
(13, not 10 — REVIEW_03.md item 2 added three more external individuals, Freya/Noor/Idris,
one per creative role Lars doesn't cover, so "Engage external" has a real option regardless of
which role is actually short. Before that, 10 not 9 — REVIEW_03.md R2.4 added Nadia, an
internal designer sharing Alex's skills, so a reassignment recommendation has a genuine second
candidate to rank against Maya instead of one candidate by construction. Before that, 9 not 8
— REVIEW_02.md P5.6 added an external motion designer so its own example recommendation
option, "Engage Lars," is reachable in the live demo, not just described.)

## Brands and markets

**Invented brand names only — no real company names anywhere in seed data, code, templates,
or documentation.** See `docs/POSITIONING.md` "Demo data rules" for the full rule; this
reverses what the original version of this document said. A parent group, Nordelva Group,
with three brands, each checked against a search for real-company collisions before use
(`docs/DECISIONS.md` round-2 review):

| Brand | Category | Lead market |
|---|---|---|
| Fotomera | photo books and prints | NL |
| Halveth | wall art and décor | DE |
| Cassenvale | personalised gifts | FR / ES |

Markets: NL, DE, FR, UK, ES. Source market is usually NL or UK.

## People

Invented first names only. Mix of internal and external, with capacity that is not all 100%
— part-time contracts are normal in studios and their absence is a tell.

| Name | Role | Capacity | Notes |
|---|---|---|---|
| Alex | Senior Designer | 80 | deliberately overloaded |
| Maya | Designer | 100 | has headroom — the reassignment target |
| Sam | Producer | 100 | tight, owns several projects |
| Elena | Motion Designer | 80 | available, holds the scarce motion skill |
| Tomas | Copywriter | 60 | part-time |
| Priya | Designer | 100 | mid-loaded |
| Nadia | Designer | 100 | shares Alex's skills, 50% free — the real second reassignment candidate |
| Jonas | Translator (DE) | external | Talent Pool — not on the capacity roster until engaged (REVIEW_02.md P5.5) |
| Camille | Translator (FR) | external | Talent Pool; deliberately *not* engaged for one FR project |
| Lars | Motion Designer | external | Talent Pool — REVIEW_02.md P5.6's own "Engage Lars" resource-option example, made reachable |
| Freya | Senior Designer | external | Talent Pool — shares Alex's skills, an external option for his own role |
| Noor | Designer | external | Talent Pool — shares Maya/Priya/Nadia's role |
| Idris | Copywriter | external | Talent Pool — an external option alongside Tomas |

Skills should be specific enough that the resource recommendation has something real to
reason about: `motion`, `retouching`, `layout`, `copy_de`, `copy_fr`, `paid_formats`.

## Required conflicts

The seed data **must** produce all five of these. Verify each on screen before calling the
seed done.

1. **Capacity overload.** Alex allocated to ~95% across overlapping assignments, one of
   which has a deadline within the current week. This drives the resource recommendation.
2. **Viable reassignment.** Maya has enough available capacity and the right skill to take
   one of Alex's projects. Without this, the recommendation has no answer.
3. **Incomplete brief.** One project sitting at status `brief` whose raw text is genuinely
   vague — missing format specs, unconfirmed audience, no approval owner, a soft deadline
   ("ideally next Friday"). Should score in the 55–70 band.
4. **Localisation bottleneck.** One project with an FR target market, no assigned
   translator, and a due date within 4 days. Drives the localisation risk flag.
5. **A performance insight worth acting on.** German creative insight rows where
   lifestyle-led variants clearly outperform product-only. Enough rows (6+) to look real,
   with a small enough sample that the recommendation's `caveats` field honestly says so.

## Distribution

Spread the 12 projects across the pipeline so the board doesn't look empty or uniform:
roughly 2 brief, 2 ready, 3 assigned, 2 in production, 1 creative review, 1 approved,
1 delivered.

Deadlines: a few inside 7 days (so the dashboard has urgency), most within 6 weeks. Anchor
dates relative to the seed run date so the demo never goes stale — a board full of overdue
work three weeks from now undermines everything.

## Creative insight rows

Per row: brand, market, format, variant theme, impressions, CTR, engagement rate,
conversion rate, period. Plausible ranges: CTR 0.6–3.0%, engagement 1–8%, conversion
0.4–2.5%. The German lifestyle-vs-product gap should be visible but not absurd — roughly
2.4% vs 1.1% CTR.

## Implementation

A `seed.py` that is idempotent: running it twice does not duplicate rows. Provide a way to
reset to a clean state — the demo will be run several times, and a polluted database
mid-presentation is a bad moment.
