# 04 — Lanes core

**Status:** Done
**Branch / PR:** `plan/04-lanes-core` · https://github.com/scotteskridge/claude-code-lanes-starter/pull/6
**Builds on:** plan 02 (kitlib, `kit` CLI, hook mode), plan 03 (root from the hook's `cwd`, decision
33); ARCHITECTURE §6 (lanes), §14, §15; decisions 2 (worktree location), 11 (lanes vs task branches),
20 (relation to Claude Code's features)

## Goal
A project lists its lanes in `.claude/kit.toml`. `kit lanes create` makes one git worktree per lane,
`kit lanes status` shows every lane at a glance, and `kit lanes remove` takes one away. When an
agent session starts in a lane folder, a hook tells it its lane, scope, owned paths, resources and
branch, and warns about drift. An edit outside the lane's paths turns into a permission prompt.

## Out of scope
- `lanes start`, `sync`, `finish`, PR-mode merge detection: plan 05.
- Wiring the two hooks into `settings.json` and the installer's lane questions: plan 08. (For the
  live check in this plan, the owner adds the hook JSON to `settings.local.json`, as in plan 03.)
- Unity resources and sibling-folder defaults for Unity: plan 10.
- Skills that read lane state (`/next`, step 0 of every skill): plan 07.

## Claude Code behaviour this relies on (docs, checked 2026-10-04)
- **SessionStart** input carries `cwd` and `source` (`startup`, `resume`, `clear`, `compact`,
  `fork`). Plain stdout, or `hookSpecificOutput.additionalContext`, is added to Claude's context.
  The hook can't block.
- **PreToolUse** can answer `hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision:
  "ask", permissionDecisionReason: "..."}`. `tool_input.file_path` is absolute. What "ask" does in
  `bypassPermissions` mode is **not documented** (the likely answer: no prompt).
- **CLAUDE.md loading walks up from `cwd` to the filesystem root.** A session in
  `<repo>/.claude/worktrees/ui/` therefore loads the lane's own `CLAUDE.md` **and the main
  checkout's** (`<repo>/CLAUDE.md`, possibly older or newer). The `claudeMdExcludes` setting skips
  named files.
- **Skills, agents and commands:** a worktree with its own `.claude/skills/` loads only that copy.
  An installed project commits its skills, so a lane uses its own copy.
- **Auto memory** is per repository and shared across worktrees (`~/.claude/projects/<project>/memory/`).
- `.worktreeinclude` is honoured only by worktrees Claude Code creates itself, so `lanes create`
  copies those files on its own.
- `CLAUDE_PROJECT_DIR`: the worktrees page says it "stays put" at the folder where the session
  started. A reported bug says otherwise for `claude -w`. The design doesn't depend on it (it uses
  `cwd`); the live check records what it is.

## Open questions
1. **Nested worktrees load the main checkout's `CLAUDE.md` too.** Two copies of the rules, one
   possibly stale, every session. *Recommendation:* keep the nested default (decision 2). When
   `lanes create` makes a lane, it adds `claudeMdExcludes` entries for the main checkout's absolute
   `CLAUDE.md` and `AGENTS.md` paths to that lane's own `.claude/settings.local.json`. That file is
   gitignored and specific to this machine. Existing keys are kept, and `lanes create` prints what
   it changed. The live check confirms it works. If it doesn't, the default becomes the sibling
   folder `../{project}-lanes` (one line in the template; the code supports both either way).
2. **Which `kit.toml` defines the lanes?** Each worktree has its own committed copy, which can lag
   the integration branch. *Recommendation:* the hooks use the lane's own copy (consistent with
   decision 33). The router warns when `git show <integration>:.claude/kit.toml` differs ("lane
   definitions changed on `main`; start your next task from it"). `create`, `status` and `remove`
   run from any folder and use the copy in that folder.
3. **How is a folder matched to a lane?** *Recommendation:* the git top level of `cwd` is compared
   with `<main checkout>/<worktree_root>/<name>`, after resolving both and comparing
   case-insensitively on Windows. The main checkout is found with `git rev-parse
   --git-common-dir`, so it works from inside a lane. No match means "not a lane": the router says
   so in one line, and the ownership check is off.
4. **What the main checkout holds** (§15). In local mode, plan 05 fast-forwards the integration
   branch with `git push . HEAD:main`, which git refuses while `main` is checked out anywhere.
   *Recommendation:* the kit never moves the main checkout on its own. `lanes status` reports what
   it holds, and in local mode warns when it has the integration branch checked out, giving the
   one command to fix it (`git switch --detach main`). PR mode doesn't care.
5. **`lanes create` details.** *Recommendation:*
   - Create from `origin/<integration>` when that ref exists, else the local branch. No fetch:
     create works offline, and the router warns when the lane is behind.
   - **Refuse** when a nested `worktree_root` isn't gitignored (`git check-ignore`), and say which
     line to add to `.gitignore`. Never edit the file.
   - An existing folder that is already this lane's worktree counts as done. Any other existing
     folder is an error.
   - Copy files that match `.worktreeinclude` **and** are gitignored, using git's own matching:
     the intersection of `git ls-files -o -i --exclude-from=.worktreeinclude` and `... --exclude-standard`.
   - `create` with no names creates every lane; `--dry-run` prints the plan.
6. **What the lane router warns about.** It uses local git data only, never blocks, stays under ~15
   lines and takes well under 1 s. *Recommendation:*
   - Detached HEAD: between tasks, run `lanes start <task>`.
   - A branch that isn't `<lane>/...`: wrong branch for this lane.
   - Behind the integration tip: `origin/<integration>` if present, else local.
   - Already merged into it: `git merge-base --is-ancestor`. Squash merges aren't detectable
     locally; plan 05 handles those.
   - Uncommitted changes left from an earlier session.
   - The `kit.toml` difference from question 2.

   On any error it **fails open but tells the agent**: exit 0, with context saying the lane check
   failed and why, and to run `kit lanes status`.
7. **The ownership hook.** *Recommendation:*
   - A separate `kit hook ownership` on Edit, Write, MultiEdit and NotebookEdit. A path in the
     lane's `owns` or `shared_paths` is allowed.
   - Any other path inside the project gets `ask`, with the reason (lane, path, what it owns).
     Paths outside the project, folders that aren't lanes, and `ownership = "off"` are allowed.
   - It **fails open** (exit 1, shown, never blocking): it reduces conflicts, it isn't security.
   - Bash and PowerShell writes aren't checked (documented).
   - The doc says ask prompts may not appear in `bypassPermissions` mode.
8. **Validating `[[lanes]]`.** *Recommendation:*
   - `name` is required. It is also a folder name and a branch prefix, so it must match
     `^[a-z0-9][a-z0-9-]*$`. Names must be unique, and none may equal the integration branch.
   - `scope` is a string. `owns` is a list of globs, at least one.
   - `resources` is a table of strings, numbers or booleans.
   - `merge_mode` is `pr` or `local`. `ownership` is `ask` or `off`. `worktree_root` may contain
     `{project}`.
   - Two lanes owning the same path is allowed (shared fixtures happen), and `lanes status` shows
     it as a note.
9. **PR state in `lanes status`.** *Recommendation:* show the open PR for each task branch via
   `gh pr list --head <branch>` when `gh` is installed and signed in, otherwise "PR: unknown". It
   never fails the command, and `--offline` skips it. Matching by head commit and closed PRs
   (§15) stay with plan 05.

## Reuse
- `kitlib/config.py`: already accepts the `lanes` table and the `[project]` lane keys; the strict-key helpers (`_check_keys`, `_fail`).
- `kitlib/globs.py` (`normalize`, `validate`, `matches_any`): `owns` and `shared_paths` matching.
- `cli.py`: hook patterns (`run_hook_protected`, fail-open `hook_rules_check`), exit codes.
- `tests/helpers.py` (`make_repo`, `git`, `run_cli`, `hook_payload`): temp repos with spaces, a bare `origin`.
- Templates: `kit.toml.tmpl`, `.gitignore.tmpl` (already ignores `.claude/worktrees/`), `.worktreeinclude.tmpl`, `parallel-lanes.md.tmpl`, `CLAUDE.md.tmpl`.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `.../kitlib/config.py` | Edit | `Lane` dataclass, `[[lanes]]` and lane `[project]` key validation (question 8) |
| `.../kitlib/lanes.py` | New | Main checkout and lane lookup (question 3); worktree paths; `create`, `remove`, `status` data (questions 4, 5, 9) |
| `.../kitlib/lane_hooks.py` | New | Router text (question 6) and ownership decision (question 7) |
| `.../kitlib/settings.py` | Edit | Merge `claudeMdExcludes` into a lane's `settings.local.json`, keeping format (question 1) |
| `.../cli.py` | Edit | `lanes create/status/remove`, `hook lane-router`, `hook ownership`. It is at 330 lines, so the hook handlers move to `kitlib/hooks.py` in the same change |
| `payload/templates/.claude/kit.toml.tmpl` | Edit | Commented `[[lanes]]` example and the `[project]` lane keys |
| `payload/templates/docs/ai/parallel-lanes.md.tmpl` | Edit | Main checkout in local mode, the `CLAUDE.md` exclusion, tools that must skip `worktree_root` (pytest `norecursedirs`, linters), ownership limits |
| `tests/test_lanes.py`, `test_hook_lane_router.py`, `test_hook_ownership.py`, `test_config.py`, `test_templates.py`, `test_cli.py` | New / Edit | See Tests |

## Steps
1. Tests then code: `[[lanes]]` validation.
2. Tests then code: lane lookup and `lanes create` / `remove` (temp repo with a bare `origin`, path with spaces).
3. Tests then code: `lanes status` (local data, `gh` stubbed and absent).
4. Tests then code: `hook lane-router` on recorded SessionStart JSON for each drift case.
5. Tests then code: `hook ownership` on recorded PreToolUse JSON.
6. Template and doc changes. Live check in a real session (the owner adds the hook JSON): router
   context, an ownership prompt, the `CLAUDE.md` exclusion, auto memory on Windows, and the value of
   `CLAUDE_PROJECT_DIR`. Record the results.
7. Fresh-context review, fix findings with tests, second review of the fixes, open the PR.

## Tests
| Test | Proves |
| --- | --- |
| `test_config` (added) | Valid lanes load. Bad names, duplicates, a name equal to the integration branch, empty `owns`, a bad glob, unknown keys and bad `merge_mode`/`ownership` values each give an error naming the key |
| `test_lanes` | `create` makes detached worktrees at the integration tip (origin preferred) and is idempotent. It refuses a non-ignored root or a foreign folder, copies only ignored files listed in `.worktreeinclude`, writes `claudeMdExcludes` while keeping existing settings, and `--dry-run` writes nothing. Sibling `worktree_root` with `{project}` works. `remove` refuses uncommitted changes. `status` reports branch, ahead/behind, dirty, unpushed, PR state or "unknown", the overlap note and the local-mode main-checkout warning. Lane lookup works from the main checkout, from a lane and from a subfolder |
| `test_hook_lane_router` | One case per drift warning. "Not a lane" in the main checkout. No `kit.toml` → silent. A broken config or crash → exit 0 with a "lane check failed" note and no traceback. Output stays under the line budget. Paths with spaces |
| `test_hook_ownership` | Owned and shared paths allowed. Out-of-lane path → `ask` JSON with the reason. Outside the project, not a lane and `ownership = "off"` → allowed. Windows `\` paths and case. Errors → exit 1, never blocking |
| `test_templates` (added) | Rendered `kit.toml` with the example lanes uncommented loads |

## Done when
- [x] Tests above pass locally (584 passed) and in CI (Windows + Ubuntu, Python 3.11 + 3.13)
- [x] Reviewer reports attached to the PR; every 🔴 fixed
- [x] Live check done, or its gaps recorded in ARCHITECTURE §15
- [x] CHANGELOG, ROADMAP, ARCHITECTURE §6 and §15, decisions log updated

## Notes after implementation
Changes from the plan:
- **`lanes remove` is in this plan** (the index listed it under plan 05): it pairs with `create`.
- **Default `shared_paths`** are the changelog fragments, backlog and plans (ARCHITECTURE §8), so
  every lane can write its own docs without a prompt; the template shows them.
- **Code layout:** `lanes.py` (lookup and per-folder state), `lane_setup.py` (create, remove),
  `lane_status.py`, `lane_hooks.py`; hook handlers moved from `cli.py` to `hooks.py`. Each stays
  under ~300 lines. The lane modules are imported lazily, so a fault there can't stop the
  protected guard (tested with a deliberately broken copy).
- **Main checkout lookup** (decision 37, revised during review): the git top level when run
  there; from a lane, git's first `worktree list` entry or a submodule's `core.worktree`, which
  must have `.claude/kit.toml` checked out. A separate git dir can't be traced back, so `create`
  refuses it. Lanes need git 2.36+.
- **Three review rounds** (each fix has a test that failed on the code before it):
  - *First* (1 🔴, 3 🟠, 8 🟡): a fresh branch fast-forwarded to the tip was reported "already
    merged"; local mode used a stale `origin/main`; edits to the main checkout or another lane
    weren't judged (now they ask, decision 44, confirmed by the owner); `remove` deleted ignored
    work (now refuses without `--force`, decision 45); Windows device names; odd `gh` output; partial
    `create` failures; case on Windows; test gaps.
  - *Second* (2 🟠, 6 🟡): `create` reported a lane "created" when `worktree add` failed, and a
    rerun didn't redo failed copies; `_merged` counted work reset away (only work since the
    branch's last creation or reset counts, plus `git am`); separate git dir named `.git` and
    submodule lanes; included folders and caches made `remove` refuse; hook speed (now one
    `rev-parse` call: router 0.62 s, ownership 0.38 s); message wording.
  - *Third* (3 🟠, 7 🟡): the cache rule matched names anywhere in a path (it deleted
    `src/venv/keys.secret`); unreadable files gave a traceback; a main checkout on a commit from
    before the kit gave a misleading error; `create` in a separate-git-dir repo; `git worktree
    prune` advice; old git; chunked file comparison; docs.
- **Live check** (Windows, Claude desktop app 2.1.286, owner's session in a `demo` lane with both
  hooks in its `settings.local.json`): the briefing appeared at start (the transcript records the
  hook's output) and after `/clear`; an owned Write went through; Writes to the lane root, another
  lane's folder and the main checkout each prompted. A read-only verifier reproduced every hook
  decision with the same paths. `claudeMdExcludes` works with forward-slash absolute paths
  containing a space: the session's loaded instructions held the main checkout's `CLAUDE.local.md`
  but not its `CLAUDE.md` in the same folder. Auto memory is shared by every lane (documented;
  lane-aware memory is on the roadmap). `CLAUDE_PROJECT_DIR` isn't set in the agent's shell; the
  hooks use `cwd`, so it doesn't matter.
- **Not shown live** (ARCHITECTURE §15, plan 08): `bypassPermissions`/`acceptEdits` with the
  ownership `ask`; Edit, MultiEdit and NotebookEdit (only Write was used); the exact prompt text;
  whether a parent folder's `.claude/CLAUDE.md` loads at all; the terminal CLI; macOS/Linux.
