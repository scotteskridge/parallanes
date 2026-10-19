---
status: idea
lane: any
size: M
---
# Open a Claude Code session per lane with one command

After `lanes create`, the owner still opens a terminal per lane, `cd`s into its folder and starts
`claude` (the installer's next steps list the folders, plan 16). A `lanes open` that does this
would remove the last manual setup step, but terminals differ on every OS (Windows Terminal,
macOS Terminal, the many Linux ones), and the trap of `claude --worktree` (decision 107) must stay
avoided.

**Done when:** `lanes open` starts one Claude Code session in each lane's folder on Windows and
macOS, or says plainly what to run where it can't.
