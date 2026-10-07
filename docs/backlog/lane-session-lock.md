---
status: next
lane: any
size: M
---
# Warn about a Claude Code session lock on a lane

`claude --worktree <lane>` locks the lane's worktree with the reason `claude session <lane> (pid N)`
and, interactive, deletes the lane's folder on exit when the session changed nothing; a `-p` run
leaves the lock behind, and `lanes remove` then fails with git's "fatal: cannot remove a locked
working tree, lock reason: claude session core (pid 20516)" (decision 107). The docs warn against
the flag and say how to unlock; the kit could catch it too:
- the lane-router could warn at session start that this session will delete the lane on exit.
  **Check live first** that the lock is written before the SessionStart hook runs (the live run only
  showed it while the session ran);
- `lanes remove` and `lanes status` could name a leftover session lock and the `git worktree
  unlock` that clears it.

Read the lock from `git worktree list --porcelain` (`locked <reason>`), not `.git/worktrees/<name>`,
whose folder name git may number. Only a lock with that reason counts: an owner's own `git worktree
lock` is theirs.

**Done when:** a lane session started with `claude --worktree <lane>` is warned at start (or the
live check shows it can't be, and the item says so), and `lanes remove`/`lanes status` explain a
leftover Claude Code session lock, with tests for each and for an owner's own lock left alone.
