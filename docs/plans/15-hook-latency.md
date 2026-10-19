# 15 — Hook latency

**Status:** Approved
**Branch / PR:** `plan/15-hook-latency` · PR link once open
**Builds on:** backlog `hook-latency` (step 4 of the v0.2 build order, decision 110); decisions 9,
33, 40, 41 (each hook's failure policy); decision 99 (the `sh` launchers and `python-path`);
decision 119 (plan 14's extra `git worktree list` in the lane-router)

## Goal
The hooks that run on every tool call cost less than half what they do now: the protected guard
and the ownership hook each take under ~150 ms of their own time on Windows, every hook's time is
measured on Windows and Linux and written down, and a test fails when a hook's imports grow.

## What the measurement showed (2026-10-19, Windows 10, Python 3.12.2, Git for Windows)
A scratch project with the kit installed and two lanes, a task started in lane `core`; median of
15 runs; "direct" is `python cli.py hook <name>`, "via sh" is the command settings.json runs.

| Hook (where) | Direct | Via `sh` | git calls |
| --- | --- | --- | --- |
| `python -c pass` | 43 ms | | |
| protected (Bash, main checkout) | 337 ms | 543 ms | 1 |
| protected (Edit, lane) | 351 ms | 532 ms | 1 |
| ownership (Edit, lane) | 579 ms | 810 ms | 4 |
| rules-check (Edit, main checkout) | 343 ms | 548 ms | 1 |
| lane-router (lane, once a session) | 1216 ms | 1420 ms | 12 |

Where the time goes, per call:
- **Each git call costs ~70 ms on Windows.** Every hook starts with `find_root`'s
  `git rev-parse --show-toplevel`; ownership then runs three more to find the lane
  (`rev-parse`, `worktree list`, `config --get core.worktree`).
- **Importing the kit costs ~130 ms:** `cli.py` imports `argparse`, `changelog`, `settings` and
  `subprocess` for every command, though a hook uses none of them; `dataclasses` (via `inspect`) is
  most of the rest.
- **The launcher costs ~180 ms:** `sh` itself starts in ~90 ms on Windows; its `$(dirname ...)`
  and `$(head ... | tr ...)` each fork more processes.
- The checks themselves (TOML parse, globs, regexes) are ~20 ms.

## Out of scope
- The lane-router's other git calls (status, drift): it runs once a session, not per tool call.
  It gains what the shared fixes give; trimming its own calls is a follow-up if it still feels slow.
- Which Python the installer records: a venv's `python.exe` on Windows is a shim that adds ~65 ms
  (`python -c pass`: 109 ms vs 43 ms). Noted in the lane guide, not changed here.
- The `kit` CLI commands' speed (`lanes status`, `next`): not per tool call.

## Open questions
1. **Finding the project root and the lane without git.** *Recommendation:* read them from disk,
   with git as the fallback. The root is the nearest folder holding `.git` (a folder, or a file in a
   linked worktree), as git itself finds it; a lane's main checkout comes from the `.git` file's
   `gitdir:` line and that folder's `commondir` file (both in git's documented repository layout),
   when the common dir is `<main>/.git`. Anything else (a `GIT_DIR` or `GIT_WORK_TREE` in the
   environment, a separate git dir, a submodule, a file that doesn't parse) falls back to today's
   git calls, so an unusual layout is slower, never wrong. That takes protected from 1 git call to 0
   and ownership from 4 to 0. *Why not just cache:* there's no process that outlives a hook call,
   and a cache file can go stale, which decision 35 avoided for lanes. *What would change this:* if
   you'd rather the security guard never read git's files itself, protected keeps its one
   `rev-parse` (~70 ms) and only ownership reads from disk.
2. **The launcher and what "150 ms" counts.** *Recommendation:* keep `sh .claude/kit/hook <name>`
   in settings.json and remove the launcher's forks (`${0%/*}` for `dirname`, `read` for
   `head | tr`), which saves ~80 ms; the 150 ms target counts the hook's own time (Python start to
   exit), and the decisions log records `sh`'s ~90 ms start on Windows as a floor the kit doesn't
   control. *Why:* changing the settings command means re-checking how Claude Code runs hook
   commands on every OS, and a migration for every installed project's settings.json, for ~90 ms.
   *What would change this:* if the end-to-end time is what you want under 150 ms, that migration
   becomes a plan of its own.
3. **The regression test.** *Recommendation:* two tests. A precise one: run each hook in a fresh
   Python and assert which kit and heavy standard-library modules it loaded (no `argparse`,
   `changelog`, `settings` or lane code in protected; no `subprocess` in protected or ownership on
   the normal layout). A coarse one: the hook path's import time, best of five, under a set limit
   (about twice the measured time after this plan) so a CI runner's noise can't fail it but a
   return of the old imports does. *Why both:* the module list catches the likely regression exactly
   and never flakes; the time limit catches a slow import nobody listed.

## Reuse
- `config.find_root` and `lanes.locate` / `_main_from_linked`: the git versions stay as the
  fallback; their tests are the contract the disk version must meet.
- `cli.main`'s import guard (`IMPORT_ERROR`) and `hooks.run`: the hook path keeps their failure
  policies (protected fails closed on any import error).
- `tests/test_hook_launcher.py`, `test_hook_protected.py`, `test_hook_ownership.py`,
  `test_lanes_edge_cases.py` (submodules, separate git dirs): existing behaviour to keep.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `kitlib/config.py` | Edit | `find_root` reads `.git` from disk first; `subprocess` imported only for the fallback |
| `kitlib/lanes.py` | Edit | `locate` reads `gitdir:` / `commondir` first; git calls as fallback |
| `cli.py`, `kitlib/hooks.py` | Edit | `hook` skips argparse and the CLI-only modules; lazy imports per hook |
| `kitlib/*` (dataclasses users) | Edit | Only if measuring shows `dataclasses` still costs >10 ms on the hook path |
| `.claude/kit/hook` | Edit | No forks: `${0%/*}`, `read` |
| `tools/hook_timing.py` | New | Dev-only script that prints the table above (not installed) |
| `tests/test_hook_imports.py` | New | Question 3's two tests |
| `tests/test_find_root.py` or existing tests | New / Edit | Disk vs git agree on every layout the suite builds |
| decisions log, CHANGELOG, lane guide | Edit | Record numbers, the `sh` floor, the venv shim note |

## Steps
1. `tools/hook_timing.py`; record the baseline above on Windows and in WSL Ubuntu.
2. Failing tests: the import tests (question 3), and disk-vs-git agreement for root and main
   checkout (main checkout, lane, nested folder, path with spaces, submodule, separate git dir,
   `GIT_DIR` set, no git).
3. Hook fast path in `cli.py` and lazy imports.
4. Disk-first `find_root` and `locate`.
5. Launcher without forks (its tests run on both OSes in CI).
6. Measure again on Windows and Linux; set question 3's limit from the result; docs.

## Tests
| Test | Proves |
| --- | --- |
| Each hook in a fresh Python: modules loaded | Hooks import only what they use |
| Hook-path import time, best of 5, under the limit | A slow new import fails the suite |
| Disk and git `find_root` agree: main, lane, subfolder, spaces, no git | Same root, no git call |
| Disk `locate` falls back: submodule, separate git dir, `GIT_DIR` set, garbled `.git` file | Unusual layouts still right |
| Existing launcher, protected, ownership, lane tests unchanged | Failure policies kept (fail closed / open) |

## Done when
- [ ] Tests above pass locally (CI reported after the merge, decision 118)
- [ ] Reviewer report attached to the PR; every 🔴 fixed
- [ ] Each hook's time per call measured on Windows and Linux, before and after, in the decisions
      log; protected and ownership under ~150 ms of their own time on Windows, or the log says why
- [ ] Live check: one `claude -p` session in a scratch project with lanes, asserting the protected
      and ownership hooks still fire (block and ask) after the changes
- [ ] CHANGELOG, decisions log and lane guide updated

## Notes after implementation
<!-- Filled in at wrap-up: what changed from the plan and why. -->
