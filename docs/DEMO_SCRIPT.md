# Demo Script — About 7 Minutes

The demo has one job: make a Creative Operations leader think *this person understands how
a studio actually runs*. Feature tours do not achieve that. A single traced thread does.
Two threads, really: resourcing (steps 3–4) and creative-intelligence-to-production (step 6),
with production planning (step 8) as a third, shorter one. If time is short, cut step 8 first
— everything before it stands on its own. See `docs/DECISIONS.md` 028 for how this script was
re-verified end to end against the live app.

**Before you start:** `python -m app.seed --reset` for a clean database, and confirm
`AI_PROVIDER=mock` in `.env` (or unset) so nothing depends on network connectivity.

## Opening — 20 seconds

State plainly what this is: an independent prototype, fictional data, built in about a day
with AI-assisted development, exploring how creative intelligence and production planning
could connect. Say it up front. Overclaiming is the only way to lose the room.

## 1. Dashboard — 40 seconds

Open on "Needs attention". With a fresh seed it reads **"4 projects need intervention this
week"** — lead with the two that carry the rest of the demo, and don't dwell on the other two:
- *Winter Campaign Refresh* is at risk — Alex is at 95% allocation against a Friday deadline → Resources
- *Autumn Prints FR Push* is blocked — the FR review has no assigned translator with 3 days to deadline → Pipeline
- (Two more — *Loyalty Relaunch Teaser* and *Loyalty App Push* — are flagged for running out
  of runway against their deadline. Real, not a bug: a deadline-proximity rule added after
  the first version of this script. Name it in passing if asked, don't spend time on it.)

The point: a producer's first ten minutes of the day are usually spent reconstructing this by
hand. Here it's already waiting.

*(One more item — a brief readiness warning — will appear here later if you revisit the
Dashboard after step 5. That's not a bug: it only shows up once a brief has actually been
scored, same as in a real studio.)*

## 2. Pipeline — 30 seconds

Show the board. Then open **"Loyalty App Push"** (Brief column) and attempt to move it
straight to **In Production**. It's refused: *"Cannot move directly from Brief to In
Production — must pass through Ready, Assigned first."* The refusal is the interesting part
— it's operational policy made mechanical, not a UI limitation.

## 3. Resource conflict — 50 seconds

On Resources, point to **Alex: 95% allocated against 80% contracted capacity — Overloaded**.
Say plainly that this number is arithmetic on assignment records, not model output — click
into a project detail page if you want to show the underlying Assignment rows. Then show the
conflict list: Alex, 95% against 80%, across *Winter Campaign Refresh* and *Loyalty Relaunch
Teaser*.

## 4. AI recommendation and approval — 50 seconds

Click **"Get AI recommendation for Winter Campaign Refresh"**. The recommendation:

> Maya holds a matching skill and has 55% available. Moving Winter Campaign Refresh from
> Alex to Maya drops Alex from 95% to 40%, protecting the Friday deadline.

**Reject it once** — the card moves to "Rejected" and stays visible in history; nothing about
Alex's allocation changes. This demonstrates rejection is a real state, not a formality.

Click **"Get AI recommendation"** again, then **Accept**. Watch the numbers move live: Alex
40%, Maya 100%. This is the "humans stay in control" argument, demonstrated rather than
asserted.

**This changes who's actually free later in the demo.** After this step, Maya is the one at
100% and Alex has the headroom — so in step 6, the production recommendation names *Alex*,
not Maya. That's the same live-capacity read doing its job twice, not an inconsistency; say so
if you're running steps out of order in rehearsal and the name doesn't match what you expected.

## 5. Brief assistant — 80 seconds

Open the Brief Assistant — it lands on **Quick Estimate**, the default mode. This fixes a
real flaw: a tool that refuses to answer until a brief is complete has failed at the job real
producers actually have. Type one sentence:

> Summer social campaign for Germany, maybe six or so assets, no shoot.

It answers immediately: an indicative duration and cost range, an earliest realistic delivery
date, and one highlighted line — the **single best question** — telling you exactly which
assumption is worth going to confirm. Point at the assumption controls underneath: change
asset count from 6 to 20 and hit **Recalculate** — the range moves instantly, no AI call made.
Say the line: these numbers read from an editable **Assumptions** library (`/assumptions`) —
the studio's own planning heuristics, day rates and review-cycle lengths, visible and
adjustable rather than buried in code.

Click the **Full Brief** tab. Paste this (or use *Loyalty App Push*'s own brief text from its
project detail page):

> Need something for the DE app push, ideally next Friday. Probably social and maybe email?
> Not sure on exact sizes yet, will confirm. Audience is existing customers I think. Who
> signs off on this one is TBC.

Show the extraction, then the readiness score — **50%, Needs clarification** — with the
rubric table visible underneath it. Point at the four missing rows (audience, format specs,
deadline confirmed, approval owner) and read out what each one blocks. This is the "identify
missing information" competence made systematic, not vibes. Give it a project name and brand,
then **Create project from brief** — it lands in the pipeline at Brief, and (per step 2's
rule) can't be pushed past Ready until those gaps close.

## 6. Creative intelligence to production — 70 seconds

**The centrepiece — give it the most time.**

On Creative Intelligence, find the **DE** card (there may be a couple of other market cards
from incidental data — DE is the one with a real sample behind it, 6 lifestyle variants).
It reads: **Lifestyle 2.37% CTR (6 variants) vs Product-only 1.10% CTR (6 variants)**.

Pick a brand, click **"Get production recommendation"**. The result:

> Produce 3 additional lifestyle-led variants for DE — 2.1 days effort, Alex has the window,
> DE copy review required before publish, awaiting approval.

(If you're running this step before step 4 in some future rehearsal order, it may name Maya
instead — see the note at the end of step 4 for why that's expected, not a bug.)

Read the caveat aloud: *"Sample size is small (n=6); treat as directional."* The restraint is
part of the argument — a lifestyle-led pattern from six variants is a lead worth acting on,
not a proven law, and the system says so instead of overselling it.

**Accept it.** Show the new project appearing in the Pipeline at Ready, then open it — the
Deliverable, the Assignment, and the Localisation row are all already attached.

Say the line explicitly: *creative intelligence tells you what is happening; creative
operations decides what to do about it. This is the bridge.*

## 7. Localisation — 30 seconds

Open **Autumn Prints FR Push** from the pipeline. Its Risk assessment panel reads: *"FR
review has no assigned translator with 3 days to deadline."* Assign a translator from the
dropdown right there — watch the risk assessment clear immediately, and the red "Risk:
Localisation" badge disappear from its pipeline card. Localisation as part of the production
workflow, not a downstream afterthought discovered too late.

## 8. Timeline and planning — 50 seconds (cut first if short on time)

Open **Timeline**. This is generated from a phase template and a deadline, not hand-entered —
back-scheduled the same way `Assumptions` is now wired into it: edit `client_review_days`
there and regenerate a schedule, and the review-phase dates actually move.

Point at **Autumn Prints FR Push**: a red "Behind" badge, and a matching red ring around a
few of its phase bars — those are staffing gaps, not date problems: no one on the roster has
spare capacity in the right role for that specific window, visible without opening anything.
Expand the row: the AI-narrated feasibility panel names the working-day shortfall and the
single phase most responsible, then lists computed options — compress a review round, drop
revisions, or move delivery — each with its own recovered days, never invented by the model.
Point at the milestone list on the right: every PPM and sign-off meeting across every
scheduled project, one list, sorted by date — the practical thing a producer takes away.

Then open an unassigned production phase and click **Assign** — the dropdown is already
filtered to people with the right role and real spare capacity for that specific window, not
just "free today." Pick one and commit it. That's a real Assignment record now, the same
table Resources already reads — nothing new to reconcile between the two screens.

## 9. Close — 30 seconds

The proposed chain versus the traditional one. The point is not removing the producer — it
is giving the producer better information and more time for the decisions only a human
should make.

---

## Presenting notes

- Run from a clean seeded database: `python -m app.seed --reset`. Reset before each run —
  accepting recommendations during rehearsal changes real state (Alex's allocation, new
  projects, who's free for step 6 and step 8's assign interaction), and you don't want to
  discover that mid-demo.
- Mock mode is fine and removes network risk. Have a key configured only if you intend to
  show a live call, and if you do, show it on the Brief Assistant, where a few seconds of
  latency reads as normal rather than broken.
- If asked what you would build next: real integration behind the existing mock boundary,
  historical capacity data to make estimates learned rather than assumed, and authentication.
  Naming what is missing reads as judgement.
- If asked how much of this you wrote: answer honestly. AI-assisted development is the
  subject of the demonstration, not something to be sheepish about. What you are showing is
  the specification, the operational logic, and the judgement about where AI belongs.
- If asked about the numbers changing session to session: dates are anchored relative to
  whenever you last ran the seed script, not hardcoded — the demo never goes stale, but the
  exact day names ("Friday") stay accurate only right after a fresh seed. Step 8 deliberately
  avoids reading exact dates aloud for the same reason — describe the pattern, not the number.
- Steps 1–7 are the same traced thread this script always had, re-verified end to end against
  a real cold start (`DECISIONS.md` 028) — every number and refusal message in them is exactly
  what the running app produces. Step 8 is new territory (Sessions B and C); if it's ever cut,
  the demo still stands completely on its own without it.
