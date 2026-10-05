# 05 — Lane task cycle

**Status:** In progress
**Branch / PR:** `plan/05-lane-task-cycle` · PR link once open
**Builds on:** plan 04 (lane lookup, `integration_tip`, `lanes status`, the router's local merge
check, `fake_gh` test helper); ARCHITECTURE §6 (task cycle), §15 (PR matching); decisions 11
(branches live for one task), 12 (PR mode default), 38 (the kit never moves the main checkout),
39, 43

## Goal
Inside a lane, an agent or a human runs three commands for each task: `kit lanes start <task>`
makes a fresh `<lane>/<task>` branch from the latest integration branch, but only after it has
proved the previous task branch was merged. `kit lanes sync` brings in new integration commits
without rewriting anything under review. `kit lanes finish` runs the tests, then either pushes and
opens a PR (PR mode) or fast-forwards the integration branch (local mode).

## Out of scope
- Writing the PR body (plan link, reviewer report): `/wrap-up` writes it and passes it with
  `--body-file` (plan 07); the reviewer is plan 06. `finish` only carries what it's given.
- Merging the PR, and deleting the remote branch afterwards (a human merges; GitHub can delete
  head branches itself).
- Network calls in the lane-router hook: it stays local-only (decision 40). Squash merges are
  detected by `start`, not the router.
- Wiring and skills that call these commands: plans 07 and 08.

## Open questions
1. **How does `start` know the previous task branch was merged?** *Recommendation:* it checks the
   branch the lane has checked out, if it's a `<lane>/...` branch, in this order:
   - Merged if its tip is an ancestor of the integration tip (merge commit or fast-forward). In
     PR mode it fetches `origin` first.
   - PR mode, otherwise: `gh pr list --head <branch> --state all --json number,state,headRefOid`,
     keeping only PRs whose `headRefOid` equals the branch tip (§15: an old PR with the same
     branch name can't count). `MERGED` means merged (this covers squash and rebase merges).
     `OPEN` means refuse: "PR #n is still open". `CLOSED` means refuse and suggest `--abandon`.
     No PR at this commit means refuse: "commits since the PR, or no PR yet".
   - `gh` missing or failing: refuse and say why. Never guess "merged".
   - `--abandon` deletes an unmerged branch on purpose and prints its tip SHA so it can be
     recovered.

   Other leftover `<lane>/*` branches are listed as a note and never deleted.
2. **What `start` does once that passes.** *Recommendation:* it refuses with uncommitted changes.
   It validates the task slug with the lane-name pattern (`^[a-z0-9][a-z0-9-]*$`, at most 50
   characters) and refuses a branch name that already exists. Then it runs `git switch --detach
   <tip>`, deletes the old branch, and runs `git switch --no-track -c <lane>/<task> <tip>`.
   `--no-track` matters: without it git sets `origin/main` as the upstream, and every "pushed?"
   check after that would be wrong. The tip is `origin/<integration>` after a fetch in PR mode, or
   the local branch in local mode (decision 39). A lane already on a detached HEAD skips the
   merge check.
3. **When does `sync` rebase and when does it merge?** *Recommendation:* it rebases when the
   branch has never been pushed, meaning `origin/<branch>` doesn't exist after a fetch (PR mode).
   In local mode it always rebases, unless that ref exists. Otherwise it merges, so it never
   force-pushes. It refuses with uncommitted changes, and on a detached HEAD it says "between
   tasks". **On a conflict it stops and leaves the rebase or merge in progress.** It lists the
   files and gives the continue and abort commands, because resolving the conflict is the work.
   It doesn't abort on its own.
4. **What `finish` does, in order.** *Recommendation:*
   1. Refuse with uncommitted changes, or with no commits ahead of the tip.
   2. `sync`, so the tests run on what will actually land.
   3. Run `test_command`.
   4. Push or fast-forward.

   **Local mode:** `git push . HEAD:<integration>`. If that's refused because another lane got
   there first, it runs sync and the tests once more, then retries once. After that it
   detaches at the new tip and deletes the merged branch, so the router shows "between tasks".
   It refuses up front while the main checkout has the integration branch checked out
   (decision 38 gives the command).

   **PR mode:** `git push -u origin <branch>`, then `gh pr create --base <integration> --head
   <branch>` with `--title` and `--body-file`. The defaults are the oldest own commit's subject,
   and a commit list. If an open PR already exists for this branch (a re-run after fixes), it
   pushes and prints that PR. It never force-pushes. If `gh` is missing after the push
   succeeded, it exits 1 and prints the URL to open the PR by hand.
5. **How `test_command` runs.** *Recommendation:* in the lane folder, through the platform shell
   (`shell=True`), so `npm test && ...` works. It comes from the project's own committed
   `kit.toml`, which is protected by decision 30. Output streams live and `finish` stops on a
   non-zero exit. A missing `test_command` means refuse. There is **no `--skip-tests`**:
   "evidence, not claims".
6. **Where the commands run.** *Recommendation:* only inside a lane folder (decision 37 lookup).
   Anywhere else they refuse with "not a lane; `cd` into `<worktree_root>/<lane>`". Each command
   prints what it did as short lines an agent can quote, and fails with exit 1 and one clear
   reason.

## Reuse
- `kitlib/lanes.py`: `find_current`, `integration_tip`, `is_ancestor`, `branch_of`, `dirty_count`,
  `git`, `LaneError`.
- `kitlib/lane_status.py` `pr_state`: the timeout and defensive `gh` JSON parsing pattern, extended
  with `headRefOid` here.
- `kitlib/lane_hooks.py` `_merged`: stays as the router's local guess; `start` uses its own exact check.
- `cli.py` `run_lanes`: lazy import and error handling. `cli.py` is at 294 lines, so the `lanes`
  parser moves into `kitlib/lane_cli.py`.
- `tests/lane_helpers.py` (`lanes_repo` with a bare `origin`, `commit`, `lane_dir`, `fake_gh`,
  `no_gh_env`). `fake_gh` gains argument logging so tests can assert what `gh pr create` received.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `.../kitlib/lane_cycle.py` | New | `start`, `sync`, `finish` (questions 2–6) |
| `.../kitlib/lane_merged.py` | New | Merged check: ancestry plus PR by head commit (question 1) |
| `.../kitlib/lane_cli.py`, `cli.py` | New / Edit | `lanes` subcommands, including `start`, `sync` and `finish` with their flags |
| `payload/templates/docs/ai/parallel-lanes.md.tmpl`, `WORKFLOW.md.tmpl` | Edit | Exact behaviour: conflicts, `--abandon`, local-mode retry, no skip-tests |
| `tests/test_lane_start.py`, `test_lane_sync.py`, `test_lane_finish.py`, `lane_helpers.py` | New / Edit | See Tests |

## Steps
1. Tests then code: the merged check against a bare `origin` and a stand-in `gh` (each PR state,
   a stale PR with the same name, no `gh`).
2. Tests then code: `start` (including `--abandon`) and `--no-track`.
3. Tests then code: `sync` (rebase vs merge, conflict left in progress).
4. Tests then code: `finish` in both modes (tests failing, race retry, existing PR, no `gh`).
5. Docs and templates. Live check: one full cycle in a real lane session, PR mode against a
   scratch GitHub repo the owner creates, plus local mode. Record the results.
6. Fresh-context review, fix findings with tests, review the fixes until a round has no 🔴, then
   open the PR.

## Tests
| Test | Proves |
| --- | --- |
| `test_lane_start` | New branch at the tip, with no upstream. Refuses when dirty, on a bad or existing slug, or outside a lane. Merged by ancestry. Merged by PR at the same head commit (squash). Refuses an open PR, a closed PR (until `--abandon`), a PR at an older commit, and no `gh`. `--abandon` prints the SHA. Leftover branches noted, not deleted. Paths with spaces |
| `test_lane_sync` | Rebases an unpushed branch. Merges a pushed one, with no force-push (origin's branch is still an ancestor). Refuses when dirty or detached. A conflict is left in progress with the files and commands listed |
| `test_lane_finish` | Failing tests stop it before any push. PR mode pushes and calls `gh pr create` with the base, title and body file. A re-run with an open PR only pushes. No `gh` → pushed, exit 1, URL printed. Local mode fast-forwards, detaches and deletes the branch. Refuses while the main checkout holds the integration branch. A race (another lane landed first) re-syncs, re-tests and retries once. Nothing ahead → refuse |
| `test_cli` (added) | Subcommands are wired and print a clean error, not a traceback |

## Done when
- [ ] Tests above pass locally and in CI (Windows + Ubuntu, Python 3.11 + 3.13)
- [ ] Reviewer reports attached to the PR; every 🔴 fixed
- [ ] Live check done, or its gaps recorded in ARCHITECTURE §15
- [ ] CHANGELOG, ROADMAP, ARCHITECTURE §6 and §15, decisions log updated

## Notes after implementation
<!-- Filled in at wrap-up: what changed from the plan and why. -->
