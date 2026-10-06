---
status: later
lane: any
size: S
---
# Offer the exact fix when a lane boundary stops something

When the ownership prompt or a lane check stops a file the task genuinely needs, the owner has to
work out the `kit.toml` edit themselves. [lanekeeper](https://github.com/kish21/parallel-agents)
prints the one command that widens the lane on purpose (`lanekeeper allow --lane x <path>`), which
refuses a path another lane owns, so the boundary changes by a recorded decision.

Reference: `docs/survey-lanekeeper.md`.

**Done when:** the ownership prompt and the lane-boundary check end with the exact change that would
allow the file (a `kit.toml` line, or a `kit lanes allow` command if one is added), and say when the
file belongs to another lane instead.
