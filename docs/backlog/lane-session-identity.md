---
status: next
lane: any
size: M
---
# Give each lane session its name, ports and notes through built-in hooks

The lane-router SessionStart hook can do more with features Claude Code already has
([hooks](https://code.claude.com/docs/en/hooks.md), [statusline](https://code.claude.com/docs/en/statusline.md)):

- return `sessionTitle: "<lane>"`, so sessions are named after their lane, findable with `/resume`,
  and reachable by name through cross-session messaging;
- append `export` lines for the lane's ports to `CLAUDE_ENV_FILE`, so Claude's Bash commands get
  them with no new CLI (the user's own terminal still needs the lane `.env`; see
  [lane-resources-env](lane-resources-env.md));
- an optional status line script that maps `workspace.git_worktree` to lane, task branch and drift;
- a gitignored `CLAUDE.local.md` per lane, written by `lanes create`, for lane-specific notes, since
  auto memory is shared by every worktree (ROADMAP §6 Later).

Not documented: whether the PowerShell tool applies `CLAUDE_ENV_FILE`. Test it on Windows. Details:
`docs/survey-claude-code.md`, Lanes.

**Done when:** a lane session is titled after its lane and its Bash commands see the lane's ports,
verified live on Windows with Bash and PowerShell; the status line and `CLAUDE.local.md` are
shipped or dropped by the owner's call.
