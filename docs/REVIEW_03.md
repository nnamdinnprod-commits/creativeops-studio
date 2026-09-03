# Owner Review — Round 3

Second full review of the deployed prototype, covering every screen plus first use of the
brief estimator.

**Read `REVIEW_02.md` first.** Its P0–P3 work largely landed and is not repeated here. What
remains from it is carried forward as R1 below, because it is still the single largest cause
of what follows.

## What has been fixed since round 2

Verified on the live site: the 540% allocation is gone and no figure now exceeds 100%; real
brand names are gone; "rows" is now "market versions"; the timeline shows 7 projects instead
of 3 (later 10 of 12, once R1 item 1 below landed); the Blocked tile is derived and shows a
real count; duplicate recommendations are resolved on the resources page; the external
translators have moved off the capacity roster; projects created from Creative Intelligence
reach the pipeline as real projects with their own pages.

That is eight of the largest items closed. The remaining list is longer but shallower.

---

## Priority

This project is a portfolio piece with a deadline, not a product. Items are marked
**[DEMO]** where a reviewer would notice within the five-minute demo, and **[LATER]** where
they would not.

**If only three things get done: R1 (now the five-item plan in that section), R2 and R4.**
Those three cover every failure a Creative Operations reviewer would spot unprompted.

---

## R1 — Finish the derived-values work **[SUPERSEDED — see "Current plan" below]**

*Carried forward from `REVIEW_02.md` P3 on the theory that it was still the root cause of
most reported problems. The audit this section asked for ran first, and it changed the plan
— kept here for the record, not as the active work item.*

**What the audit found.** The stored-value list turned out to be short: most of what
`REVIEW_02.md` P3 flagged had already been fixed in earlier rounds (`DECISIONS.md` 012, 019,
021, 032, 034, 042, 043, 045 all moved a figure from "computed once and stored" to "computed
live"). Two genuinely derived, stored columns remained real: `ProjectPhase.assigned_person_id`
(a denormalized mirror of an `Assignment` row, kept in sync by discipline across three call
sites, not a constraint) and `Project.estimated_days` / `Project.project_type_id` — not stale,
just never written by `brief.py`'s Full Brief flow at all. A few more (`Project.risk_level`,
`risk_reason`, `ProjectPhase.status`, `Deliverable.status`) turned out to be dead: no writer
anywhere, harmless, worth deleting on the same pass rather than a separate reason to reopen
this file.

**What the audit disproved.** Three of the five confirmed instances above are not
stored-value drift at all — the fix here would not have touched them:

- **"0 at risk" alongside 5 blocked** — `app/routes/dashboard.py`'s at-risk filter excludes
  the "brief" attention cause outright, so a project flagged for low readiness counts toward
  neither tile and reads as on-track. A live filtering gap, not a stored value.
- **The DE localisation card's self-contradiction** — `summarize_by_market()` computes its
  headline from the single worst-flagged row and its translator list from every row in the
  market, and the template renders both as if they describe the same thing. Both facts are
  correctly computed live; the card just conflates two different rows.
- **Re-analysing an edited brief returns the original score** (R5.1) — `/brief/analyse`
  already recomputes from scratch on every submission. The real cause is `mock_analyse_brief`'s
  extraction: deadline matching only recognises a weekday name (no date-format handling), and
  approval-owner matching is one exact regex. An edit the mock doesn't recognise produces the
  same score honestly, not a stale one.

Two of the five *were* the audited kind, and both are now fixed (see R6 below, which absorbed
this work): a Brief-Assistant-created project never got a `project_type_id` or
`estimated_days`, so it could never generate a schedule or be caught by the Blocked tile's
brief-stalled check — the actual cause of "pipeline changes reach the dashboard but not
resources, timeline or planning" and half of the "0 at risk" symptom.

**The one thing that really was automatic-reschedule scope** — a status change to Waiting on
Client pushing downstream phases out on the timeline — is still real and still unbuilt; folded
into R3.3 below, since it's the same "what happens to a schedule when work pauses" question.

### Current plan (supersedes R1, absorbs R6)

Agreed sequence, one commit per item:

1. **Consolidate project creation** (R6) — one function every project-creation path calls,
   guaranteeing type, estimate, deadline, deliverables, localisation rows, and a generated
   schedule. **Done.** `app/services/project_creation.py`'s `finalize_project()`, called from
   `brief.py` and `recommendations.py`; `app/seed.py` backfills type and schedule for the seed
   projects that lacked one. Timeline coverage went from 6 of 12 to 10 of 12 (the remaining
   two are still-vague Brief-status projects with no deliverables to infer a type from — see
   R8's coverage note).
2. **Dashboard at-risk filtering** — `dashboard.py`'s at-risk filter excludes the "brief"
   cause; fix the filter so a project flagged in the attention panel is never silently
   bucketed as on-track. **Done.** The filter now counts every attention cause not already
   claimed by Blocked; a new test locks the invariant that on-track + at-risk + blocked
   always equals active, against the full seed dataset.
3. **Mock extraction quality** — widen `mock_analyse_brief`'s deadline and approval-owner
   matching, add localisation deadline to the rubric, and fix `mock_insight_to_action`'s
   identical-output-per-brand problem (R10) at the same time — both are the same underlying
   weakness (thin mocks) in the mode that gets demoed. **Done.** Deadline matching now
   recognises real date formats, not just weekday names; approval-owner matching covers
   several phrasings; localisation gained its own deadline field, extracted and scored
   separately from the project deadline. R10 verified as a side effect of the same pass —
   see its own section below.
4. **Localisation card** — rewrite `summarize_by_market()`'s output shape so the card states
   one coherent fact instead of two true facts about different rows. **Done.** Market cards
   are now clickable (filter the grid to that market) and carry an inline "Assign
   translator" action; the self-contradiction is fixed by scoping `translator_ids` to the
   same row the headline describes.
5. **Stored-column cleanup** — the audited part of the original R1: compute
   `ProjectPhase.assigned_person_id` and `Project.localisation_required` at render instead of
   storing them; delete the dead `risk_level`, `risk_reason`, `ProjectPhase.status` columns.
   **Done**, with one correction the audit above got wrong: `Deliverable.status` turned out
   to have real writers and a real reader (`project_detail.html`) — not dead after all — so
   it was kept rather than deleted, logged as a correction rather than silently done.

**Parked, then resolved:** two pre-existing test failures in `test_assignment.py`, found
while verifying item 1. Diagnosed after item 5 as instructed — one was a real, live bug
(`phase_candidates()`'s lead-time check ran for internal people too, who have no lead time to
enforce; once the real clock passed the tests' hardcoded dates it silently excluded every
internal candidate from a started phase) and is fixed; the other was confirmed as a stale
test expectation and updated to match the (correct) current behaviour. Neither was deleted to
make the suite pass.

---

## R2 — Open the resourcing model **[DEMO — R2.1 and R2.4 done, R2.2/R2.3/R2.5 open]**

Every recommendation currently resolves to Alex, and when it cannot, it declares the problem
unsolvable. Both stem from the same cause: the system can only see a closed list of eight
people, against twelve projects. It is structurally short of capacity, so it will always
fail eventually.

### R2.1 The tool must never dead-end **[DONE]**

A recommendation currently reads:

> No internal or external candidate can take this on in time — the deadline itself is the
> only lever left.

That is false, and a producer knows it is false. There are always three levers:

- **Time** — move the deadline
- **Money** — bring in external resource
- **Scope** — three variants becomes two

**Every resource recommendation presents all three**, even when one is clearly best:

> **A · Engage external** — Lars, motion, €550/day × 2 days = €1,100, available Wed (3-day lead)
> **B · Reduce scope** — 2 variants instead of 3, delivers on the original date
> **C · Move delivery to 14 Sep** — no cost, client conversation required
>
> Recommended: A — the deadline is external and the cost is small against the media spend behind it.

**Done.** `reduce_scope` added as a fourth `ResourceOption` kind, computed whenever the
conflicted project has more than one deliverable — always available alongside
reassign/engage_external/move_delivery, not just when reassignment fails. The old "the
deadline is the only lever left" message is now unreachable except in the genuine
single-option case. See `DECISIONS.md` 055.

### R2.2 Resources include companies, not just people

Add a resource type: **individual** or **company**. A film production company, a design
studio, a localisation agency. Companies are modelled differently — capacity as concurrent
projects rather than a percentage, a project or day rate band, and a longer lead time.

### R2.3 Adding a resource takes twenty seconds, from wherever you are

Fields: name, type, skills, rate, lead time, note. Available two ways:

- From the resources page directly
- **Inline within a recommendation** — "None of these work · Add a resource" opens the same
  short form, and the recommendation recomputes with the new option included

That second path is the important one. It converts the dead end into what a producer
actually does at that moment.

### R2.4 Why everything lands on Alex **[DONE]**

Two likely causes, both worth checking:

- **Seed skills are too narrow.** If Alex is the only person with a given specialism, every
  job needing it correctly goes to him. Give two or three people overlapping skills so there
  is a genuine choice to reason about.
- **The ranking has no distribution factor.** Among qualifying candidates, prefer whoever
  has the most headroom and say so: *"Maya — same skills, 40% free against Priya's 15%."*

Diagnostic: *"When recommending a resource, how many candidates typically qualify and what
determines the ranking among them? Show me the actual candidate list for the DE variants
recommendation."* One candidate means it is the skills. Five sorted by ID means it is the
ranking.

**Done, both causes.** Nadia (designer, sharing Alex's skills) added so a genuine choice
exists to rank; ranking now prefers whichever qualifying candidate has the most headroom and
names the runner-up's own headroom in the rationale ("Maya — same skills, 40% free against
Priya's 15%"), suppressed when the top two tie so it never states a number that didn't
actually decide anything. See `DECISIONS.md` 053.

### R2.5 Localisation uses the same pool

Two translators for four markets, with NL having none, makes that work unassignable by
construction. Translators come from the same pool with the same inline add — including
agencies, since localisation is usually bought from a company.

---

## R3 — Blocks need a reason, an owner and a destination **[DEMO]**

The Blocked tile now derives correctly, but a blocked project gives no reason. "Blocked" is
a status; it is not information.

### R3.1 Every block carries three things

> **Blocked** — awaiting client PO · owner: Sam · chase before Thursday or the shoot date moves

Reasons worth supporting: awaiting client approval · awaiting budget or PO · awaiting brand
or legal sign-off · brief incomplete (naming the missing fields) · no resource on a started
phase · localisation stalled · upstream dependency late.

Derived where the system already knows (brief incomplete, no resource assigned); set by the
user where it does not (budget, client), capturing who is being waited on.

Shown on the pipeline card, the project page, and the blocked list.

### R3.2 Routing by reason

**Blocks caused by someone outside the studio move columns. Blocks caused by something
inside the studio stay put and get flagged.** The first is a chasing problem, the second is
a doing problem, and they go to different people.

| Reason | Destination |
|---|---|
| Awaiting client approval / feedback / PO | **Waiting on Client** column |
| Awaiting brand or legal sign-off | **Waiting on Client**, owner named |
| Brief incomplete | stays in stage, flagged |
| No resource on a started phase | stays in stage, flagged |
| Localisation stalled | stays in stage, flagged |
| Upstream dependency late | **Waiting on Client** if external |

**Store `previous_status` on the move.** When the block clears, the project returns to the
stage it came from rather than the producer having to remember.

### R3.3 What happens to allocations when work is blocked

The naive answer — free the capacity — is wrong. The work returns, usually at short notice,
and if those people have been backfilled there is nobody available. Leaving everyone
allocated is also wrong, because idle people show as busy.

**Model the hold explicitly:**

- Moving to Waiting on Client asks: hold the allocations, or release them? **Hold is the
  default.**
- Held allocations render distinctly and count toward a separate **provisional** figure
  alongside committed.
- Capacity reads: *"Maya — 60% committed, 40% held on Loyalty App (waiting on client since 28 Aug)."*
- A hold running past a threshold (default 10 working days) prompts a suggestion to release.

This is a judgement the tool surfaces rather than makes, and it is the kind of decision a
producer will recognise immediately.

---

## R4 — The estimator's cost model is structurally wrong **[DONE, R4.1/R4.3/R4.4; R4.2 still LATER]**

A multi-brand US film shoot returned **€20,000–45,000**. That is off by roughly an order of
magnitude, and any Creative Operations reviewer will know it on sight. This is the single
most damaging inaccuracy currently in the application.

**Cause:** the estimator prices internal people at day rates and nothing else — phases ×
roles × rates. Correct for a social batch made in-house; wrong for anything involving a
production.

### R4.1 Minimum version — roughly two hours **[DONE]**

**Built with one deliberate departure, logged in `DECISIONS.md` 057**: base-plus-marginal
instead of the flat multiplier specified below — a one-time production base (paid once,
regardless of brand count) plus a flat per-brand marginal figure, because the marginal cost
of one more brand's incremental production needs doesn't scale with how expensive the shared
set happens to be, which a flat multiplier on the whole total would otherwise imply. The
bands, territory factors and their values below are exactly as specified and exactly as
seeded. Verified live: a representative six-brand US film brief (the literal brief referenced
here wasn't recoverable from history) now lands at €241,250–€619,270 total, versus
€20,740–€43,500 before.

Add to the Assumptions library, and use whenever a brief involves a shoot:

**Production scale tiers** (planning bands, editable)

| Tier | Band |
|---|---|
| Tabletop / studio product | €15k–40k |
| Single location, lifestyle | €40k–100k |
| Multi-location or talent-led | €100k–300k |
| Large-scale international | €300k+ |

**Territory factor** (planning multipliers, editable)

| Region | Factor |
|---|---|
| US | 1.45 |
| UK / Nordics / CH | 1.25 |
| Western Europe | 1.0 |
| Southern Europe | 0.85 |
| Central / Eastern Europe | 0.7 |

**Multi-brand factor** — `1 + 0.25 × (brands − 1)`. Six brands in one production is not six
productions; shared setup, crew and location are the entire reason anyone consolidates a
shoot. A producer will check whether this is modelled.

That alone moves the US estimate into a defensible range, which is what the demo needs.

### R4.2 Full version **[LATER]**

Replace the tier band with line items: production company and director fee · crew · talent
and usage buyout · location and permits · equipment · travel and accommodation · post
(offline, online, grade, audio, VFX) · music licensing · insurance and contingency.

### R4.3 Two rules for both versions **[DONE]**

**Show internal effort and external spend separately.** They come from different budgets and
producers think about them differently. One merged number is less useful than two.

**Name the dominant variable:** *"Talent buyout across six brands is the largest single swing
in this figure."* Built exactly as specified — Python compares the three real components
(internal effort, base production cost, brand premium) and names whichever is genuinely
largest for that estimate, so the wording only appears when the number backs it up.

Both built into a shared `_compute_estimate_block()` that Quick Estimate and the Full Brief
Assistant both call — one calculation, not a lookalike copy on each screen (`DECISIONS.md`
058). A follow-up beyond the original spec: one editable sentence stating what the figure
does and doesn't include (covers production/crew/location/equipment/post; excludes talent
buyout and usage, travel, music, insurance, media spend, agency fees), shown next to the
number on both screens (`DECISIONS.md` 059).

### R4.4 The boundary that stays **[DONE]**

These are the studio's own planning assumptions, editable and labelled as such — **not a
claim to authoritative market rates.** Same rule as everything else in `ASSUMPTIONS.md`. The
roadmap answer remains real production intelligence via trade bodies and film commissions,
described as a next step rather than implemented.

---

## R5 — Estimator interaction **[DEMO — R5.1 done via R1 item 3; R5.2/5.3/5.4 open]**

### R5.1 Re-analysis returns a stale score **[DONE]**

A brief scoring 65% was edited to add the missing deadline, localisation deadline and
approval owner. Re-analysing returned 65% again, unchanged, including after navigating away
and back.

Diagnostic: *"When I re-analyse an edited brief, does it re-run extraction and recompute the
score, or return a stored result? Show me where readiness_score is written and where it is
read."* **Answered by the R1 audit: it already re-runs extraction and recomputes on every
submission — the stale-looking score is a mock-extraction gap (rigid deadline/approval-owner
matching), not a stored result.** Covered by item 3 of the current plan under R1.

### R5.2 Fill the gaps in place

Rather than sending the user back to edit prose, show each missing field as an input beneath
the score:

> **65% — needs clarification**
> Final localisation deadline `[______]`
> Approval owner `[______]`
> Homepage banner specs `[______]`
> → **Update**

Score recomputes on submit. Faster for the user, and it captures answers as structured data
rather than prose that has to be re-extracted — so more reliable as well as nicer. Make this
the primary path; keep text editing as the fallback.

### R5.3 Show the estimate's shape

The estimator returns a duration but no picture of it. Phase templates and a timeline
renderer both already exist — render the estimate's phases as a small horizontal strip
showing where PPM, shoot, review and delivery fall. A component drop, not a feature.

### R5.4 Read the stated timing

A brief saying "next year, probably spring" was ignored; the estimator forward-scheduled from
today. Extract vague timing as a target window and show both directions:

> If you started Monday: delivers 12 December.
> Against your stated spring window: you would need to start by 6 January.

The second line is what turns an estimate into a plan.

---

## R6 — A project created from a brief must arrive complete **[DONE]**

*Absorbed into the "Current plan" under R1 above as item 1 — done first, since it turned out
to be the cause of the largest single symptom in R1's list.*

Creating the project is not sufficient. It must arrive with everything attached, or it exists
but is inert.

On creation from a brief or an estimate, the project must have:

- Project type and volume factor, so phases can generate
- Deadline
- Deliverables with market and format
- Localisation rows for every target market
- Generated schedule phases
- Candidate assignments derived from those phases

And must immediately appear in: the pipeline at the correct stage · dashboard active and
at-risk counts · the timeline with its phases · the localisation grid if it has target
markets · resource allocations for anyone assigned.

**Done.** `app/services/project_creation.py`'s `finalize_project()`, called from both
`brief.py` and `recommendations.py`. Volume factor is the one bullet left as-is (stays at its
default of 1.0) — deriving one from a Full Brief's deliverables needs an asset-count concept
that flow doesn't currently ask for, a separate, undecided question rather than something to
guess at silently. Verified live: a project created through `/brief/analyse` +
`/brief/create-project` gets a type, a generated schedule, and shows on `/timeline` without
reloading anything by hand.

---

## R7 — Localisation page **[DEMO — first three bullets done; last depends on R2.5, still open]**

The grid works and links correctly to project pages. The four market cards above it do not.

- **Market cards become interactive** — clicking one filters the grid to that market. **Done.**
- **The action sits on the card** — a card reading "no assigned translator, 4 days to
  deadline" carries an **Assign translator** button. **Done**, as a separate inline `<form>`
  beside the card's own link rather than nested inside it.
- **Fix the self-contradiction** in the DE card — item 4 of the current plan under R1. **Done**
  — `translator_ids` now scoped to the same row the headline describes.
- **Translators come from the open pool** (R2.5) — still open; the translator dropdown reads
  from the existing translator roster, not yet the same wider pool R2.5 would open up.

---

## R8 — Timeline interactivity **[LATER, except the today line]**

- **The today marker does not move.** It is almost certainly positioned at a fixed offset
  rather than computed from the current date each render. Two-line fix. **[DONE]** — confirmed
  live: `timeline.html`'s marker position is `timeline.today_pct`, computed by the route on
  every request, not a stored or hardcoded offset.
- **Scroll through time** — horizontal scroll with project names pinned left, a range control
  (4 weeks / 8 weeks / quarter), and a **Today** button that snaps the view back
- **Per-project timeline** — cheaper than it sounds, because project pages already exist.
  Add a phase strip to the existing project page rather than building a new screen
- **Click a date column** to see everything happening that day
- **Coverage** — **[DONE, R1 item 1]** was 7 of 12, now 10 of 12 after the project-creation
  consolidation backfilled a type and a schedule for every project that had deliverables to
  infer one from. The remaining two (Loyalty App Push, Retouch Guidelines Refresh) are still
  at status Brief with no deliverables at all — genuinely nothing to schedule, not a bug.

---

## R9 — Assumptions page **[R9.1/9.2/9.3 done; R9.4 still LATER]**

### R9.1 The labels are raw database keys **[DONE]**

`client_review_days`, `volume_scale_7_15`, `confidence_high_low_factor`. This is the same
failure as "rows", one layer deeper. Every row needs a human label with the key hidden:

> **Client review round** — 3 days
> *How long a standard client review takes*

Single highest-value change on this page.

### R9.2 Confidence bands: eight rows becomes four **[DONE]**

They control how wide an estimate is when the brief is vague, so a guess never reads as a
quote. The concept stays; the raw multiplier pairs go. Express as what the user sees:

| When the brief is | Estimate shown as |
|---|---|
| Fully specified | −5% / +10% |
| Mostly specified | −15% / +25% |
| Partly assumed | −25% / +40% |
| Mostly assumed | −40% / +70% |

### R9.3 Volume scaling needs its reason **[DONE]**

> **Volume scaling** — effort grows more slowly than asset count, because setup is a fixed
> cost. Twenty assets take roughly 2.5× the time of six, not 3.3×.

### R9.4 Lead times are far too thin

Four rows across five mediums. Expand, grouped by medium with collapsible sections, showing
only the groups relevant to a project's type when the estimator uses them.

**Approvals and business affairs — any project**
Brief to kickoff · strategy input · brand review · legal review · business affairs
contracting · budget or PO approval · new supplier onboarding

**Film and branded content**
Treatment development · production company bidding · director availability · casting ·
location scouting and recce · location permits · talent contracts and buyouts · crew booking
· equipment hire · music licensing · stock and archive clearance · voiceover booking ·
offline edit · online and grade · audio mix · rights clearance sign-off

**Event**
Venue confirmation · fabrication · freight and logistics · health and safety assessment ·
rehearsal scheduling · onsite build

**Stills**
Photographer booking · studio booking · model casting · usage rights negotiation · prop and
wardrobe sourcing · retouching turnaround

**Social and AI-generated**
Platform spec confirmation · generation iteration cycles · synthetic likeness and voice
clearance · AI content disclosure review · community and legal review

**Localisation**
Translation turnaround · in-market review · market legal review · subtitling · dubbing and
VO · cultural adaptation review

The AI-specific group is worth having even though it is newest — synthetic likeness clearance
and disclosure review are real lead times now, and accounting for them signals a current
mental model rather than a 2019 one.

---

## R10 — Creative Intelligence mock differentiation **[DEMO — mock differentiation done, live-key test not done]**

Selecting any of the three brands for Germany returns a word-for-word identical
recommendation. That is a single canned mock response being returned regardless of input,
and it is the most visible "this is not real" tell on the site — anyone who clicks two brands
knows immediately.

Two things, do both:

- Key the mocks by brand, market and variant theme so different selections genuinely differ.
  **Done** — `compute_brand_breakdown()` computes a real per-brand CTR comparison from actual
  insight rows, and the mock narrates that instead of a canned response; verified live that
  Fotomera/Halveth/Cassenvale each return genuinely different numbers and rationale for the
  same DE market.
- Test with a live API key, since behaviour may differ between modes and it must be known
  which mode is being demoed. **Not done** — every verification this round ran with
  `AI_PROVIDER=mock`; a live-key comparison for this specific path remains open.

The significance threshold from `REVIEW_02.md` P6.2 still applies: surface an insight only
where the gap is large enough and the sample big enough, and say "no significant variance
this period" otherwise.

---

## R11 — Copy and display **[DONE]**

| Current | Change to | Status |
|---|---|---|
| "1 of 6 over capacity · 1 tight · 4 available" | Name them. **"Alex is over capacity · Maya is tight · 4 have room"** — at six people, counts are abstraction for no reason, and each name should link | **Done** — each name links to its row on `/resources` |
| Raw keys on the Assumptions page | Human labels (R9.1) | **Done** — see R9.1 |
| "0 at risk" beside 5 blocked | Fix the at-risk filter — item 2 of the current plan under R1 | **Done** — see the current plan's item 2 above |

---

## Verification

All five checks in `SUPERVISION.md`, the eight in `REVIEW_02.md`, plus — re-verified live
against a real cold start as part of the final pass before this round shipped:

1. **A project created from a brief appears on all five surfaces** without manual reloading —
   **verified** (R6, done since the "Current plan" pass)
2. **Every blocked project states a reason, an owner and a consequence** — **not built** (R3
   entirely open)
3. **A resource recommendation offers time, money and scope options** — never a dead end —
   **verified** (R2.1)
4. **A new resource can be added inline from within a recommendation**, and the
   recommendation recomputes to include it — **not built** (R2.3 open)
5. **Two different brands on Creative Intelligence produce different recommendations** —
   **verified**: Fotomera/Halveth/Cassenvale each returned a genuinely different CTR
   comparison and rationale for the same DE market and period in this round's rehearsal (R10)
6. **Re-analysing an edited brief changes the score** — **verified** (R5.1/R1 item 3)
7. **A US shoot estimate lands in a defensible range** — a producer reading it should not
   wince — **verified**: a representative six-brand US film brief now lands at
   €241,250–€619,270 total, versus €20,740–€43,500 before (R4)
8. **The today marker sits on today** — **verified**: computed live from the current date,
   not a fixed offset

Then `python tools/audit.py --url <site>` and `/check-honesty` before sharing.
