---
status: later
lane: any
size: S
blocked_by: plan 12
---
# Say in the README what the kit adds over Claude Code's built-ins

Claude Code now does plain parallel worktrees itself (`--worktree`, desktop worktree sessions,
`.worktreeinclude`, isolation from the main checkout, base-branch sync, PR watching). A reader
will ask "why not just use that?" The answer is the layer on top: lanes with owned paths and
resources, the start → sync → finish cycle that tests the exact commit that lands, enforcement
from one config, and the plan → implement → wrap-up skills.

Readers may also know [lanekeeper](https://github.com/kish21/parallel-agents), which solves the
same problem for any agent by gating the merge. The positioning: *lanekeeper stops the merge; the
kit stops the edit and runs the whole task loop*, with long-lived lanes that suit resources like an
editor instance per lane.

**Done when:** the README has a short "Claude Code does / the kit adds" table and one honest line
on lanekeeper, checked against
the current docs at release time, with links.
