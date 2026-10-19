# 14 — Claude Code session locks on lanes

**Status:** Approved
**Branch / PR:** `plan/14-lane-session-lock` · PR link once open
**Builds on:** backlog `lane-session-lock` (step 4 of the v0.2 build order, decision 110); decision
107 (lanes are opened by their folder; `claude --worktree <lane>` warned against); decision 40 (the
lane-router briefs and never blocks); decision 45 (`lanes remove` protects ignored work);
ARCHITECTURE §6, §15 ("Can `claude --worktree <lane>` start a lane session?")

## Goal
When a lane is opened with `claude --worktree <lane>`, the agent is told at session start that this
session may delete the lane's folder on exit, so it can tell the owner before it happens. When a
headless run leaves Claude Code's lock behind, `lanes status` names it and `lanes remove` clears it
instead of failing with git's "cannot remove a locked working tree".

## What the live probe showed (2026-10-19, Claude Code 2.1.293, Windows)
Two throwaway repos, each with a lane worktree at `.claude/worktrees/core` and a SessionStart hook
that recorded what it saw, run with `claude -p "..." --worktree core`:
- The lock is already written when the SessionStart hook runs: `git worktree list --porcelain`
  shows `locked claude session core (pid N)` for the lane.
- `N` is `claude.exe` itself, an ancestor of the hook process, alive while the hook runs.
- After the `-p` run exits, the lock is still there and `N` is gone: a leftover lock.

So the backlog item's "check live first" is answered: the warning at start is possible.

## Out of scope
- Stopping `claude --worktree <lane>` or its delete-on-exit: Claude Code's behaviour, documented
  (decision 107); the kit warns.
- The desktop app's worktree sessions: their lock reason isn't known; only the reason format above
  counts (follow-up if the trial shows another).
- An owner's own `git worktree lock`: never named, never cleared.

## Open questions
1. **How to tell a running session's lock from a leftover.** *Recommendation:* check whether the
   lock's pid is alive: `os.kill(pid, 0)` on macOS/Linux, `OpenProcess` + `GetExitCodeProcess`
   through `ctypes` on Windows (standard library; never `os.kill` there, which ends the process).
   When the check can't tell, count it as alive (the cautious answer). *Not* "is it this session's
   ancestor": walking the process table is a different call per OS for little gain, since a lane
   has one session at a time. *What would change this:* a reused pid makes a leftover look alive;
   the message then says "a Claude Code session (pid N)" rather than claiming it is this one.
2. **What `lanes remove` does with a leftover lock.** *Recommendation:* clear it itself
   (`git worktree unlock`) when the pid is confirmed gone, say so in its output, then remove as
   usual (the uncommitted-changes and ignored-files checks still run first). A lock whose pid is
   alive, or can't be checked, is refused with the session's pid and what to do: close that
   session, or `git worktree unlock <folder>` if it's gone. *Why:* the leftover is the kit's known
   case and the fix is one safe command; asking the owner to type it is the lag they've asked to
   cut. *What would change this:* if you'd rather the kit never touch a lock, it prints the command
   instead.
3. **The router's wording.** *Recommendation:* one line in the briefing's Warnings, so the agent
   relays it: running lock → "This lane was opened with `claude --worktree core` (Claude Code's lock,
   pid N): on exit Claude Code deletes the lane's folder if nothing changed, ignored files (`.env`,
   local settings) included. Tell the user now; open lanes from their folder instead (decision
   107)." Leftover lock → "A Claude Code session lock (pid N, no longer running) is left on this
   lane: `lanes remove` clears it." The briefing stays within decision 103's ~15 lines.

## Reuse
- `lanes.registered_worktrees` and `lane_cycle._nobody_holds`: parse `git worktree list --porcelain
  -z`; the new parser reads the `locked` field from the same call.
- `lane_hooks.drift`: the briefing's Warnings list; one more check there.
- `lane_status.status` (calls `registered_worktrees` once for every lane) and `format_status`.
- `lane_setup.remove`: the existing checks run before the unlock.
- `tests/live/claude_run.py` and `test_shared_path_modes.py`: how a live check runs `claude -p` in
  a trusted scratch project.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `kitlib/session_lock.py` | New | Parse a worktree's lock from porcelain; match `claude session <name> (pid N)`; pid liveness per OS |
| `kitlib/lanes.py` | Edit | One porcelain read that returns each worktree's path and lock reason |
| `kitlib/lane_hooks.py` | Edit | The briefing warning (running / leftover) |
| `kitlib/lane_status.py` | Edit | A lane with a Claude Code lock shows it, with the pid and whether it runs |
| `kitlib/lane_setup.py` | Edit | `lanes remove` clears a leftover lock, refuses a running one |
| `templates/docs/ai/parallel-lanes.md.tmpl` | Edit | What the warning means; `lanes remove` clears leftovers |
| `tests/test_session_lock.py`, lane tests | New / Edit | See Tests |
| `tests/live/test_session_lock.py` | New | The live check below |
| ARCHITECTURE §6/§15, decisions log, CHANGELOG | Edit | Record it |

## Steps
1. Failing tests: parsing (Claude lock, owner's lock, no lock, a path with spaces), pid liveness
   (this process alive, a finished child's pid gone), router, status and remove.
2. `session_lock.py` and the porcelain reader in `lanes.py`.
3. Router warning, `lanes status` field, `lanes remove` unlock or refusal.
4. Docs: lane guide, ARCHITECTURE, decision, CHANGELOG.
5. Live check: `claude -p --worktree core` in a scratch project with the kit installed; assert the
   briefing (the hook's output in the stream) carries the running-lock warning; then `lanes status`
   names the leftover and `lanes remove core` clears it and removes the lane.

## Tests
| Test | Proves |
| --- | --- |
| Parse a `claude session core (pid 123)` lock; an owner's `git worktree lock --reason x`; no lock | Only Claude Code's reason counts |
| Liveness: `os.getpid()` alive; a child that has exited is gone; an unparsable pid counts as alive | The check on this OS, failing cautious |
| Router with a running lock (this test's pid) / a leftover lock (an exited child's pid) / an owner's lock | Right warning, none for the owner's |
| `lanes status` with each kind | Names a Claude Code lock and whether it runs |
| `lanes remove` with a leftover: unlocks, removes, says so | The fix, with the usual checks first |
| `lanes remove` with a running lock, and with an owner's lock | Refused with the pid; owner's lock untouched (git's own refusal) |
| `lanes remove` with a leftover lock and uncommitted changes | Refused for the changes; the lock stays |

## Done when
- [ ] Tests above pass locally and in CI (Windows + Ubuntu)
- [ ] Reviewer report attached to the PR; every 🔴 fixed
- [ ] Live check in `tests/live/` run with `--live`: the warning reaches a `--worktree` session, and
      `lanes remove` clears the lock it leaves
- [ ] CHANGELOG, ARCHITECTURE §6/§15 and decisions log updated

## Notes after implementation
- **As planned**, with the three recommendations (decision 119). `lanes.worktree_locks` reads each
  worktree's lock reason from the porcelain call `registered_worktrees` already made, so `lanes
  status` still runs `git worktree list` once; the router adds one call (~35 ms on Windows).
- **The running-lock warning comes first** in the briefing's Warnings: it is the one the agent must
  act on before the session ends.
- **`lanes remove --force` still refuses a running session:** `--force` is about ignored files, and
  removing the folder under a live session would be the delete the warning is about.
- **Live check** (`tests/live/test_session_lock.py`) passed on its first run (Claude Code 2.1.293).
