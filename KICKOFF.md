# Kickoff

## Before you start

1. Install Python 3.11+ and Claude Code.
2. Put this folder somewhere sensible, e.g. `~/Documents/creativeops-studio`.
3. In a terminal, from inside the folder:

```bash
git init
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
cp .env.example .env
claude
```

An API key in `.env` is optional. The app is required to run without one.

## Paste this as your first message to Claude Code

---

Read `CLAUDE.md` and every file in `docs/` before doing anything else.

We are building CreativeOps Studio V1 in one day. You are in Phase 1 of
`docs/BUILD_PLAN.md`. Produce the architecture proposal only — the stack confirmation,
folder structure, model sketch, route list, template inventory, AI service interfaces, and
the risk list. Do not write application code yet.

Two things about me you should factor in: I am a Creative Operations professional, not a
software engineer, so explain your reasoning in plain language and tell me when something
breaks rather than working around it silently. And the one-day budget is real — if you
think something in the docs cannot be built in the time available, say so now rather than
discovering it at 4pm.

When the proposal is ready, stop and wait for my approval.

---

## During the build

- After each phase, Claude Code should stop and tell you what works. Load the app yourself
  and look before approving the next phase.
- Use `/phase-done` at each boundary — it runs the checks from the build plan.
- If something breaks twice in the same way, `CLAUDE.md` tells Claude Code to stop and
  report rather than keep guessing. Let it. Trying a third variation is how afternoons
  disappear.
- Commit at every phase boundary: `git add -A && git commit -m "Phase N: ..."`. If a phase
  goes badly you want a working state to return to.

## What to watch for

You do not need to read the code to supervise this well. Check these instead:

- **Do the numbers move?** Accept a resource recommendation and confirm the capacity
  percentages actually change. If they don't, the accept handler is cosmetic.
- **Does the app run with no API key?** Unset it and reload. Everything should still render.
- **Is the disclaimer on every screen?** Click through all five.
- **Does an invalid action get refused?** Try moving the incomplete brief into production.
- **Does the demo path work from a cold start?** Fresh terminal, fresh database. Do this
  before you stop for the day, not on the morning of the interview.

## If you run out of day

`docs/BUILD_PLAN.md` has a cut list in priority order. Take from it rather than extending
the day — and record what you cut in the README under known limitations. A stated
limitation reads as judgement. A silently missing feature reads as an unfinished build.
