# Owner Review — Round 2

Review of the deployed prototype at `creativeops-studio.onrender.com`, verified against the
live site on 31 August 2026.

**How to use this file.** Work top to bottom. The sections are ordered by dependency, not by
screen — roughly twenty reported problems trace back to seven underlying causes, and fixing
them in this order means each fix lands on ground that is already stable. Fixing symptoms
screen by screen will not work here: the same bug is visible in six places.

Do not start a section before the one above it verifies.

---

## P0 — Brand names (do this first, before anything else)

**Problem:** the deployed site uses real company brand names attached to invented
performance metrics, on a public URL being sent to prospective employers. This is a
trademark and reputation risk, not a styling preference.

`DEMO_DATA.md` currently permits this. **That guidance was wrong for a deployed public
site and is hereby revoked.** Amend both `DEMO_DATA.md` and `POSITIONING.md` so the rule
reads: invented brand names only, no real company names anywhere in seed data, code,
templates, or documentation.

**Replacement set** — a parent group with three brands, each with a different lead market so
the localisation story still works:

| Old | New | Category | Lead market |
|---|---|---|---|
| *(group)* | **Halden Group** | parent | — |
| Albelli | **Fotomera** | photo books and prints | NL |
| Photobox | **Printhuis** | wall art and décor | DE |
| Hofmann | **Kadora** | personalised gifts | FR / ES |

Alternates if any collide with a real company: *Lumera*, *Bindwell*, *Papeterie*,
*Momentbox*, *Foldhaus*. Check each chosen name against a search before committing —
landing on a real small company recreates the same problem.

**Verify:** search the entire repository, including documentation and git history, for the
three old names. Zero results. Reseed and confirm the live site shows only the new names.

---

## P1 — Anchor all seed dates to the seed run date

**Problem:** the dashboard reports *"Autumn Prints FR Push — 29 working days behind"*.
Projects are permanently overdue and drift further every day the site exists. Every risk
flag, every deadline warning and every schedule assessment is therefore judged against dates
that were fixed at some point in the past.

`DEMO_DATA.md` already required relative anchoring. It was not implemented.

**Fix:** every date in the seed is computed as an offset from the seed run date. No literal
dates anywhere in `seed.py`. A project due "this Friday" is `next_friday(today)`, not
`2026-09-04`.

**This matters more than it looks**, because of how the site is hosted. Render's free tier
wipes the filesystem when the service sleeps, so the database is reseeded on every cold
start. With relative anchoring, that means **the demo re-anchors itself to today, forever** —
a recruiter opening the link in six weeks sees a current, coherent board. Make this
deliberate and note it in `DECISIONS.md`.

**Verify:** reseed. No project is more than 2 working days behind. Deadlines are spread
across the coming six weeks with two or three inside the next seven days.

---

## P2 — One source of truth for capacity

**Problem:** the Resources page shows Alex three different ways simultaneously — the table
says 40% and Available, the conflict below says **540% against 80% contracted**, and the
accepted recommendation refers to 95%. The dashboard compounds it: *"0 of 8 over capacity"*
sitting directly above *"Alex is at 540% allocation"*.

**Diagnosis:** capacity is being computed in more than one place with different definitions.
540% is the signature of schedule-derived assignments (added in the planning session) being
summed on top of the original seeded assignments, each claiming a full share of the same
days. `CLAUDE.md` requires that `app/services/capacity.py` is the only place this is
calculated.

**Fix:**

1. Find every place allocation or utilisation is computed. There should be one. Delete the
   others and route through `capacity.py`.
2. Establish why assignments are double-counted. Schedule-derived assignments must replace
   seeded ones for the same project, not stack on them.
3. Define the window explicitly and use it consistently — allocation "this week", or "over
   the assignment period", but the same definition everywhere it is displayed.
4. Historical recommendation text keeps its original figures. That is correct and should
   stay, but label it as at-time-of-recommendation so it does not read as a live number.

**Verify:** every allocation figure on Resources, Dashboard, Timeline and the project page
agrees for the same person on the same date. No figure exceeds a plausible maximum. The
over-capacity count matches the number of people the table shows as over capacity. Add a
unit test asserting a person's allocation is identical whichever service path computes it.

---

## P3 — Make everything write through and recompute

**This is the largest item on the list and the cause of more than half the reported
problems.** Currently, actions change the thing they touch and nothing else.

Reported symptoms, all the same underlying cause:

- Accepting a resource recommendation does not update capacity figures elsewhere
- Assigning a translator on the localisation page does nothing
- Assigning a resource on the project page does nothing
- Changing a value in the Assumptions library does not reschedule affected projects
- Pipeline status changes do not update the dashboard
- Everything appears unassigned after actions that should have assigned it

**Fix:** every mutating action runs inside one transaction that applies the change and
invalidates whatever derives from it. Concretely:

| Action | Must also update |
|---|---|
| Accept resource recommendation | assignments, capacity for both people, project risk, dashboard counts, timeline |
| Assign translator | localisation row, project risk, dashboard localisation panel, the translator's allocation |
| Assign resource on project page | assignments, capacity, timeline phase, dashboard |
| Change an assumption | reschedule every affected project, recompute phase dates, recompute risk |
| Change pipeline status | project status, dashboard counts, at-risk calculation, blocked derivation |

Nothing derived may be stored where it can drift. If a figure is displayed, it is computed
at display time from the underlying rows.

**Verify — this is supervision check 1 extended.** For each row of that table: record the
downstream figure, perform the action, hard-reload, confirm the figure changed. A single
action whose consequence is invisible fails this section.

---

## P4 — Give generated artefacts state

**Problem:** recommendations and insights are stateless, so they regenerate endlessly.
Requesting a production recommendation for the same insight produces an identical
recommendation every time; the Resources fix from round 1 was applied only to resource
recommendations and never reached Creative Intelligence.

**Fix:**

- **One pending recommendation per conflict or insight.** Requesting again returns the
  existing one. If the underlying facts are unchanged, say so rather than calling the model
  again: *"Existing recommendation still current — nothing has changed since it was
  generated."*
- **Insights carry state:** `new` / `recommendation_pending` / `actioned` / `dismissed`.
- **An actioned insight shows its outcome:** *"→ Created Campaign Y · in production · Maya
  assigned · delivers 12 Sept."*
- **`dismissed` requires a reason.** Deciding not to act on an insight is a legitimate
  outcome the system should record rather than keep raising.

Accepted and rejected items remain in history untouched — that history is the audit trail.

**Verify:** request the same recommendation three times. One record exists. Accept it. The
source insight shows as actioned with a link to what it created. The request control is no
longer offered.

---

## P5 — Wiring and coverage gaps

### P5.1 Project pages reachable from everywhere

Project detail pages exist and work — `/projects/5` renders correctly — but are linked from
almost nowhere. Build one shared template partial for a project reference and use it in
every location a project is named: pipeline cards, dashboard attention items, resource
assignments, timeline rows, localisation rows, creative intelligence outputs, recommendation
text.

Cheapest high-impact item on this list.

### P5.2 Timeline shows all projects

Currently 3 of 16. Show every project from Ready onwards. Ready projects render lighter or
outlined to distinguish planned from committed work. Projects missing a type or deadline
need both so phases can be generated — that is the reason they are absent.

### P5.3 Pipeline: separate sequence from readiness

Movement between stages is currently sequential-only. That is wrong: a market re-version, a
copy swap, a resize or an artwork resend can legitimately go straight to Creative Review or
Delivered.

**Sequence becomes free** — any stage to any stage, forwards or backwards.

**The readiness gate stays**, but scoped by a new project field:
`fast_track` / `standard` / `full_production`. Fast-track items skip the gate entirely. A
full-production project entering production without format specifications is still refused,
with the reason naming what is missing and what it blocks.

This preserves the strongest feature on the screen while fixing the wrong behaviour. It also
supports a better demo line: *the system knows the difference between a campaign and a copy
swap, and only applies the gate where it is warranted.*

### P5.4 Project lifecycle states

Add `on_hold`, `cancelled`, `waiting_on_client` and `archived`.

**`waiting_on_client` matters most.** Creative Review currently conflates "we are reviewing"
and "they are sitting on it", and those are entirely different situations. Distinguishing
*we are late* from *they are late* is among the most useful things a producer can bring to a
stakeholder conversation, and it makes at-risk logic considerably smarter — work blocked on
a client is not a capacity problem and should not be triaged as one.

Status changes to hold, cancel, or backwards capture a reason.

### P5.5 External resource — talent pool and engagements

**Problem:** two external translators sit permanently on the capacity roster at 0%. That was
a misreading of the requirement.

**What is actually needed:** the ability to bring in external resource of any role, on
demand, when internal capacity runs out — which is how studios actually absorb overflow.

Two separate concepts:

- **Team** — contracted internal people. Always on the roster, always counted.
- **Talent pool** — the external network. Role, skills, day rate, lead time, availability.
  Not on the capacity roster until engaged.

A pool member appears in resource planning only for the duration of an active engagement,
visibly marked as external with an end date, then returns to the pool.

**Two properties make this credible and both are required:**

- **Lead time.** A freelancer cannot start tomorrow. Every pool member carries a realistic
  onboarding lead.
- **Cost.** Internal capacity is sunk; external is marginal spend. That trade-off is the
  decision a producer is actually making.

Day rates and lead times live in the Assumptions library.

**Move Jonas and Camille into the pool.** Do not delete them.

Localisation translator assignment routes through this same engagement flow — one mechanism,
three screens.

### P5.6 Resource recommendations return options, not a single action

A real decision has alternatives with different costs. Change `recommend_resource` to return
a ranked set:

> **A · Reassign to Maya** — no cost, available Thursday, has not worked this brand before
> **B · Engage Lars (external, motion)** — €550/day × 2 days, 3-day lead time, available Wednesday
> **C · Move delivery to 8 Sept** — no cost, no resource change, client conversation required
>
> Recommended: A.

Choosing between those is the judgement the tool exists to support, and it is a much
stronger demonstration of "AI recommends, human decides" than a single take-it-or-leave-it
suggestion.

---

## P6 — Product framing

### P6.1 The application only delivers bad news

Every screen leads with problems. Seven attention items, everything overdue, no path to
improvement. A user never experiences having made anything better — which undercuts the
product's central claim.

Largely resolved by P3, but make it visible deliberately:

- When an action resolves a risk, **say so**: *"Risk cleared — FR review assigned to
  Camille, delivery protected."*
- The dashboard shows what was resolved recently, not only what is outstanding.
- Attention item counts go **down** visibly as things are handled.

The localisation screen is the clearest example: see the bottleneck → assign a translator →
status advances → risk clears on the dashboard. A complete positive loop in four clicks, on
a page that currently does nothing.

### P6.2 Creative Intelligence — shrink and sharpen

The page currently generates a recommendation for every brand-market combination, producing
identical generic output regardless of selection. **First check whether the mock for
`insight_to_action` varies by brand, market and variant theme, or returns one canned response
for all inputs.** A single canned mock would explain the symptom exactly.

Beyond the bug, the page is trying to be an analytics product and cannot be one. Reduce it:

- **A significance threshold.** Surface an insight only where the performance gap is large
  enough and the sample big enough to mean something. Everything else reads *"No significant
  variance this period."* Restraint is what distinguishes analysis from output.
- **The metrics table demotes** to a supporting panel labelled with an explicit reporting
  period — *"Reporting period: 17–30 August"* — with a period selector. Creative performance
  reporting is periodic in reality, so labelling it accurately makes it correct rather than
  broken.
- **The page leads with the hand-off**: insight → recommendation → the project it created.

**Decision rule for this page:** by the end of this session, accepting a recommendation must
create a project that can be clicked into, seen on the timeline, and watched move through
the pipeline. If that works, this is the most distinctive screen in the application. If it
still does not, cut the page, move the single best insight onto the dashboard as a panel,
and stop investing in it.

### P6.3 The Blocked tile

Permanently zero, because no state can populate it. Do not remove it — **derive it** from
the states added in P5.4:

- Waiting on client beyond the agreed review window
- Brief below readiness threshold and past its intended start date
- Localisation stalled with no translator assigned
- A scheduled phase that has started with nobody assigned

Clicking the tile opens the filtered list. "What is stuck, and why" is the question a
producer opens a dashboard to answer.

---

## P7 — Copy, display and deployment

### Copy fixes

| Current | Change to |
|---|---|
| "2 of 25 rows approved overall" | "2 of 25 market versions approved" — the word *rows* is a database term and must not appear in the interface |
| "aggregate utilisation 49%" | Lead with the distribution: **"0 of 8 over capacity · 1 tight · 7 available"**, demote the aggregate to a smaller second line with a hover explaining the calculation |
| "Mother's Day Static Set" scheduled 2–23 September | Mother's Day falls in March or May across these markets. Rename the project or move it. A Creative Operations reviewer will notice. |

Sweep all templates for database vocabulary leaking into user-facing copy — *rows*,
*records*, *entities*, *null*, *IDs*.

### Deployment

**Pages timed out on first request during this review.** If any page makes AI calls during
page load, a cold visitor sees a spinner or an error. Generate behind an explicit control,
or cache. Never on page load.

**Per-application tracking.** Rather than logging IP addresses — which is personal data under
GDPR, requires a privacy notice, and does not reliably identify anyone — add a `?ref=` query
parameter and count hits per ref. One link per application tells you precisely what you want
to know, with no personal data involved.

### Mobile

A "does not embarrass you" pass, roughly an hour, not full optimisation:

- Dashboard, Resources, Localisation and project pages stack cleanly on narrow screens.
  The dashboard matters most — it is the landing page.
- Pipeline: horizontal scroll with snap points, or a stage selector showing one column.
- Timeline: horizontal scroll with project names pinned left. This is the standard solution
  and is perfectly acceptable.

Anything beyond that is deferred.

---

## Deferred, deliberately

**Production intelligence** — unions, right-to-work, filming permissions, business affairs by
market. Correct direction for a real product; out of scope here because any version buildable
now would be invented or stale, and incorrect regulatory guidance in a portfolio piece
circulating among industry people is worse than an absent feature. The Assumptions library is
the honest version. See `ASSUMPTIONS.md` for the wording to use when presenting it.

**Full mobile optimisation.** **Drag and drop.** **Authentication.** **Real integrations.**

---

## Verification before calling this done

All five checks in `SUPERVISION.md`, plus:

1. **No real brand names** anywhere in the repository or git history.
2. **No project more than 2 working days behind** after a fresh seed.
3. **Every allocation figure agrees** across every screen for the same person and date.
4. **Every row of the P3 write-through table verified by hand** — act, reload, confirm the
   downstream number moved.
5. **A recommendation requested three times produces one record.**
6. **Every project name in the application is a link** that reaches the project page.
7. **The timeline shows every project from Ready onwards.**
8. **At least one complete positive loop is demonstrable end to end** — assign a translator on
   the localisation page and watch the dashboard risk clear.

Then run `/check-honesty` before the site is shared with anyone.
