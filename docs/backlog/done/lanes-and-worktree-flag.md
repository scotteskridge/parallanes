---
status: next
lane: any
size: S
---
# Check how lanes work with `claude --worktree`

Lanes already live at `.claude/worktrees/<lane>`, where `claude --worktree <name>` looks, and
reusing a name opens the existing worktree. So `claude -w core` might start a session in a lane
directly, which would be a one-line way to start a lane. But the reopen rules may reset a clean
worktree to the default branch, and they treat branches Claude Code didn't create differently
([worktrees: reuse a worktree name](https://code.claude.com/docs/en/worktrees.md#reuse-a-worktree-name)).
Also check: the built-in isolation checks against the main checkout alongside the ownership hook,
`${CLAUDE_PROJECT_DIR}` staying at the main checkout for hooks, and the desktop app's worktree sessions.

**Done when:** a live run in a scratch project (path with a space, Windows) shows what
`claude -w <lane>` does at each lane state (between tasks, on a task branch, with changes), the
results are in ARCHITECTURE §15, and the lane docs either recommend it or warn against it.

**Outcome:** decision 107, ARCHITECTURE §15. `claude -w <lane>` opens the lane unchanged at every
state and the kit's hooks work there, but Claude Code adopts the lane as its own worktree and on
exit deleted a clean lane's folder without asking; `-p` runs leave a lock that blocks `lanes
remove`. `parallel-lanes.md` warns against the flag; detecting the lock is `lane-session-lock`.
