---
status: next
lane: any
size: S
---
# Say in the README what the kit adds over Claude Code's built-ins

Claude Code now does plain parallel worktrees itself (`--worktree`, desktop worktree sessions,
`.worktreeinclude`, isolation from the main checkout, base-branch sync, PR watching), and a named
worktree is reused across sessions with its dependencies intact, so persistence alone is not the
kit's case (decision 98). A reader will ask "why not just use that?" The answer is the layer on
top: lanes with owned paths (resources come in v0.2), the start → sync → finish cycle that tests
the exact commit that lands, enforcement from one config, and the plan → implement → wrap-up
skills.

Readers may also know [lanekeeper](https://github.com/kish21/parallel-agents), which solves the
same problem for any agent by gating the merge. The positioning: *lanekeeper stops the merge; the
kit flags the edit as it happens and runs the whole task loop*.

An outside review (decision 98) found the process docs can read as over-engineered for a one-user
tool. The README must carry a reader in about two minutes: the story, the table, what the trial
caught; the plans and decisions stay as depth for anyone who digs.

Also from `docs/survey-claude-code.md`: the kit's reviewer checks against the plan, rules and
checklists, while bundled `/code-review` and `ultrareview` hunt bugs; managed Code Review never
blocks a merge, so the kit's checks stay the gate.

**Done when:** the README has a short "Claude Code does / the kit adds" table and one honest line
on lanekeeper, checked against the current docs at release time, with links, plus what the trial
caught ([the write-up](../trial/two-lane-trial.md)), linked to the published trial repo's plans,
reviews and merges (decision 104), and a first-time reader gets the point in about two minutes.

**Done (plan 12):** the README leads with the story, a "Claude Code does / parallanes adds" table
checked against the current docs on 2026-10-07 (with links), the lanekeeper line, and what the
trial caught, linked to the published trial repo. A fresh reader given only the README scored it
4/5 for "gets the point in two minutes"; its gripes were fixed. `tests/test_readme.py` runs the
quickstart as written.
