---
description: Audit the app against the positioning and ethical constraints
---

Audit this repository against `docs/POSITIONING.md`. This is a portfolio piece that will be
shown to hiring managers, so overclaiming or ambiguous framing is a real risk, not a
theoretical one.

Check and report on each:

1. **Disclaimer** — present in the footer of every rendered screen, and in `README.md`.
2. **Naming** — no repo, module, class, route, template or database object named in a way
   that implies ownership by or affiliation with a real company.
3. **Mock boundaries** — every module simulating an external service is named `mock_*`,
   lives in `app/services/mock/`, and says so in its first docstring line. Every UI surface
   fed by one is labelled.
4. **No live third-party calls** — check for HTTP clients and confirm no request goes to any
   third party's real endpoints. The LLM provider is the only permitted external call.
5. **Demo data labelling** — every table or chart drawing on seed data is marked as demo
   data. No invented figure is presented in a way that could be mistaken for a real
   reported metric.
6. **Secrets** — no API key, token or credential in any tracked file. Confirm `.env` is
   gitignored and check the git history, not just the working tree.
7. **README framing** — describes the project as an independent prototype with fictional
   data, states it was built with AI assistance, and lists known limitations.

Report each as pass or fail with the specific file and line for any failure. Fix failures
in categories 1, 2, 3, 5 and 7 directly. For 4 and 6, report first and wait — a committed
secret needs a decision about history rewriting, not an immediate commit.
