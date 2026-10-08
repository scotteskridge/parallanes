---
status: next
lane: any
size: S
---
# Offer the exact fix when a lane boundary stops something

When the ownership prompt or a lane check stops a file the task genuinely needs, the owner has to
work out the `kit.toml` edit themselves. [lanekeeper](https://github.com/kish21/parallel-agents)
prints the one command that widens the lane on purpose (`lanekeeper allow --lane x <path>`), which
refuses a path another lane owns, so the boundary changes by a recorded decision.

Reference: `docs/survey-lanekeeper.md`.

**Seen in the two-lane trial (F8, F11):** an api task needed `data/` added to `.gitignore`, which
no lane owns. The agent asked first, the hook stopped the edit, and pre-commit refused the commit
even after the owner said yes. The documented bypass, a hand commit with `KIT_ALLOW_CROSS_LANE=1`,
was tried by the driving session, and Claude Code's own safety check blocked landing it. So the
change was dropped, and the trial's `main` doesn't ignore `data/`. An approved `/wrap-up` rule hit
the same wall (`.claude/rules/` is in no lane).
Repo-wide files (`.gitignore`, `package.json`, rules) come up in every web project, so this is now
`next`. Pair it with [shared-path-modes](../shared-path-modes.md): an `ask` mode with a steward lane
fits these files.

**Done when:** the ownership prompt and the lane-boundary check end with the exact change that would
allow the file (a `kit.toml` line, or a `kit lanes allow` command if one is added), and say when the
file belongs to another lane instead.
