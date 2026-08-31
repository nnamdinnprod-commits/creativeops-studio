# Positioning and Ethical Constraints

The rules in this file are not stylistic. Getting them wrong turns a strong portfolio
piece into a liability during a hiring process. They override every other consideration.

## What this project is

An independent Creative Operations prototype exploring how AI, creative intelligence and
production planning could work together in a modern multi-market creative studio.

## What it is not, and must never claim to be

- Software belonging to, commissioned by, or affiliated with any real company
- Connected to any real company's internal systems, data or accounts
- An implementation of any real company's documented internal workflows
- A working integration with any third-party creative analytics platform

## Required disclaimer

This exact text appears in the application footer on every screen, in `README.md`, and on
the first slide of any presentation built from this project:

> Prototype concept — fictional demonstration data, based on publicly available
> information about creative operations workflows. Not affiliated with or connected to any
> company's systems.

Where third-party analytics concepts are referenced, add:

> Creative intelligence features are conceptual mock-ups based on publicly documented
> capabilities of commercial creative analytics platforms. No integration exists.

## Naming rules

- The product is **CreativeOps Studio**. Internal working name: Creative Operations
  Intelligence Hub.
- Never name the product after a real company.
- Never name a repo, database, class, route or file after a real company in a way that
  implies ownership.

## Demo data rules

**Invented brand names only. No real company names anywhere in seed data, code, templates,
or documentation.** This reverses the original rule, which permitted publicly known consumer
brand names as fictional tenants on the theory that it made the demo more legible to a
reviewer in the sector. That reasoning did not hold up once the prototype was a public URL
sent to prospective employers: real brand names attached to invented performance metrics is
a trademark and reputation risk, not a styling choice, and the risk does not go away because
the audience is expected to be sympathetic. See `docs/DECISIONS.md` for the round-2 owner
review that revoked it, and `docs/DEMO_DATA.md` for the current tenant names.

- Brand names must be invented, and checked against a search before use — landing on a real
  (even small, even obscure) company by coincidence recreates the same problem.
- All projects, people, deadlines, budgets, performance metrics and insights are invented.
- No real employee names. Invented first names only, no surnames that map to real people.
- Performance figures must be plausible but clearly synthetic. Never present a number that
  could be mistaken for a real reported metric.
- Any table or chart sourced from seed data carries a "Demo data" label.

## Mock integration rules

- Every function simulating an external service is named `mock_*` and lives in
  `app/services/ai/mock.py`, the one module every AI-calling route imports it from.
- Its docstring states in the first line that it returns synthetic data.
- The UI labels every surface fed by it.
- No HTTP request is ever made to a third party's real endpoints.

## Interview honesty

When presenting this, describe it accurately: a prototype built in roughly a day with
AI-assisted development, using invented data, to demonstrate operational thinking. The
strength of the piece is the thinking, not a claim of production readiness. Overclaiming
is the single fastest way to lose the credibility this project is meant to build.
