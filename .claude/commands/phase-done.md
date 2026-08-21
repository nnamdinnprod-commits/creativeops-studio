---
description: Verify a build phase's exit criteria before moving on
---

Verify that the current phase of `docs/BUILD_PLAN.md` is genuinely complete.

Do this by execution, not by reading code:

1. State which phase you believe we are in.
2. Run the application. Confirm it starts without error.
3. Load every screen the phase touched and confirm it renders with real data.
4. Run `pytest` if any tests exist yet.
5. Work through that phase's exit criteria one by one and report pass or fail for each.
6. Confirm the non-negotiables in `CLAUDE.md` still hold — in particular the disclaimer on
   every screen, and that the app runs with no API key set.

Then report in this shape:

- **Works:** what a user can actually do now
- **Stubbed:** what looks finished but isn't wired up
- **Failed:** any exit criterion not met
- **Time check:** are we on, ahead of, or behind the build plan's clock — and if behind,
  which item from the cut list you recommend dropping

If any criterion fails, stop. Do not start the next phase. Fix or explicitly agree to cut.
