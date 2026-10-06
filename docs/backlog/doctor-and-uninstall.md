---
status: later
lane: any
size: M
---
# Add `doctor` and an uninstall command

Two things build trust in a tool that edits a repo: a way to find what's wrong, and a clean way out.
[lanekeeper](https://github.com/kish21/parallel-agents) has both: `doctor` finds orphaned state
(stale worktrees, ports still reserved, records that disagree), and `uninit` shows a plan, asks,
removes its files and worktrees, and never deletes an unmerged branch. The kit has `lanes status`
and `lanes remove`; uninstall is on the ROADMAP as Later.

**Done when:** `kit doctor` reports lane worktrees git no longer knows (or that are missing),
settings out of sync with `kit.toml` (as `kit check settings` does), a missing or broken
`python-path`, and taken lane ports; and an uninstall command lists what it would remove, asks, and
keeps project-owned files and unmerged branches.
