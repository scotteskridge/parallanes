# Architecture

How the kit is put together, and how a project looks once the kit is installed. This is the design
every plan builds against; *why* each choice was made is in `decisions-log.md` (numbers in brackets,
e.g. [11], point there). Claude Code behaviour cited here was checked against the official docs on
2026-10-04 (links at the end); anything not confirmed is listed under *Open questions*.

## 1. Principles

1. **Put each rule where its guarantee matches its importance.** A preference goes in prose; a
   must-never goes in a deny rule or a hook; a must-always goes in CI. The agent can drift from prose
   under pressure; it can't drift from code.
2. **Deterministic where possible, agentic where it pays.** Scripts do anything with one right answer
   (git, file layout, checks). The agent does what needs judgement (planning, review, filling project
   specifics during `/onboard`). [17]
3. **Evidence, not claims.** Every guardrail has tests; every workflow has an eval; every merge has
   a test run behind it. [16]
4. **The repo is the source of truth.** Lanes, rules and process are committed files shared by
   everyone who clones the repo, not settings in someone's personal app.
5. **Never surprise the owner.** The installer never overwrites without asking; agents never settle a
   design question silently; nothing is pushed or merged without a visible step.
6. **Stdlib Python 3.11+ only** in anything installed into a project. [3]

## 2. Two things to keep apart

| | **The kit repo** (this repo) | **An installed project** |
| --- | --- | --- |
| What it is | The source: payload, installer, packs, tests, evals | Any repo the kit was installed into |
| Who edits it | Kit maintainers | The project's team and its agents |
| Its own agent setup | `AGENTS.md`, `CLAUDE.md` for building the kit | Generated from the kit's templates |

## 3. Kit repo layout

```
claude-code-lanes-starter/
├── install.ps1 · install.sh        thin bootstrappers: check prerequisites, run kit_setup.py   (plan 08)
├── kit_setup.py                    the installer (dry run, questions, manifest)                (plan 08)
├── payload/
│   ├── kit-owned/                  copied as-is; mirrors target paths; replaceable on update
│   │   └── .claude/
│   │       ├── kit/                Python: kitlib, lanes, checks, hook entry points           (02–05)
│   │       ├── skills/<name>/SKILL.md                                                          (07)
│   │       ├── agents/reviewer.md                                                              (06)
│   │       └── review/universal.md      the universal review checklist                         (06)
│   ├── templates/                  rendered once ({{placeholders}}), then project-owned        (01)
│   │                               every file ends in .tmpl, stripped on install
│   └── placeholders.toml           the placeholder registry: name, description, example        (01)
├── packs/<name>/                   optional stack add-ons, same kit-owned/templates split      (10)
├── examples/hello-lanes/           small Python project installed with the kit                 (11)
├── evals/                          scenario tests that drive `claude -p`                       (11)
├── tests/                          pytest for everything above
└── docs/                           ARCHITECTURE, ROADMAP, decisions log, plans
```

The code tested is the code shipped: tests import from `payload/kit-owned/.claude/kit/` directly.

## 4. An installed project

```
my-project/
├── AGENTS.md                      P  universal rules for any coding agent
├── CLAUDE.md                      P  "@AGENTS.md" + Claude-specific parts, under ~100 lines
├── .claude/
│   ├── kit.toml                   P  project config: test command, lanes, checks, protected paths
│   ├── settings.json              P  permissions (deny rules generated from kit.toml) + hook wiring
│   ├── rules/*.md                 P  path-scoped rules (`paths:` frontmatter)
│   ├── skills/<name>/SKILL.md     K  /plan-feature /implement /wrap-up /code-health /design /next /onboard
│   ├── agents/reviewer.md         K  fresh-context reviewer (read-only; hook in its frontmatter)
│   ├── review/*.md                K/P checklists: universal.md (K), project.md (P), <pack>.md (K)
│   ├── kit/                       K  cli.py + kitlib (lanes, checks, hooks); manifest.json; VERSION;
│   │                                 `hook` and `kit` launchers; python-path (this machine's
│   │                                 interpreter, gitignored, copied into lanes by .worktreeinclude)
│   └── worktrees/<lane>/             lane worktrees (gitignored)
├── .worktreeinclude               P  gitignored files copied into each new worktree (settings.local.json, .env)
├── .githooks/pre-commit          K  `check all --staged` before each commit (opt-in, decision 25)
├── kit · kit.cmd                  K  shims (if plan 08 keeps them): `kit lanes status`, `kit check rules --staged`
├── .github/workflows/kit.yml      P  CI: tests + checks on every push and PR                     (plan 09)
└── docs/
    ├── ai/WORKFLOW.md             P  the human guide: the daily loop and why each rule exists
    ├── ai/parallel-lanes.md       P  the lane workflow for humans: setup, the task cycle, conflicts
    ├── plans/  (+ finished/)      P  one file per plan (YYYY-MM-DD-slug.md), from _TEMPLATE.md
    ├── backlog/<slug>.md          P  one file per backlog item                                    [13]
    ├── changelog.d/<lane>-<task>.md  P  changelog fragments, compiled into CHANGELOG.md at release [13]
    ├── health/<date>-<area>.md    P  /code-health reports, one per run                         [88]
    ├── CHANGELOG.md · CODE-STANDARDS.md        (BUILD-STATE.md arrives with /sync-state [21])
    └── design/  decisions-log.md · VISION.md and DESIGN.md as optional stubs [22]
```

**K** = kit-owned, **P** = project-owned.

### Ownership and updates [7]

- Kit-owned files are listed in `.claude/kit/manifest.json` with the kit version and a SHA-256 of each
  file as installed. A future `kit update` replaces a kit-owned file only if its hash still matches
  (nobody edited it); edited files are reported, never overwritten.
- Project-owned files are rendered once and never touched again by the kit.
- To customize a kit-owned skill, copy it to a new name. The README says so.

## 5. Where instructions live

| Layer | Loaded | Guarantee | Holds | Budget |
| --- | --- | --- | --- | --- |
| `AGENTS.md` | every session, every agent tool | prose | universal rules, stack, how to check work | ~80 lines |
| `CLAUDE.md` | every Claude session; re-read after compaction | prose | `@AGENTS.md`, skills list, lane pointer, compaction notes | ~100 lines total |
| `.claude/rules/*.md` | when a matching file is read or edited | prose | area rules (`paths:` globs) | ≤200 lines each |
| Skills | name and description at start; body when invoked | procedure | workflows | one screen |
| Reviewer subagent | when called; separate context | independent check | review checklist | — |
| Permission deny rules | every tool call | enforced for built-in tools and recognized shell file commands | protected paths, secrets | — |
| Hooks | lifecycle events | enforced, deterministic | pattern rules, lane context, command backstop | fast (<1 s) |
| CI | every push and PR | enforced at the repo boundary | tests + the same checks | — |

Claude Code also reads `AGENTS.md` natively when no `CLAUDE.md` exists; the kit ships both, with
`CLAUDE.md` importing `AGENTS.md`, so the rules exist in one place. [4]

## 6. Lanes

### Concepts [11]

- **Lane:** a long-lived workspace. It has a name, a scope, the paths it owns, its own worktree
  folder, and its own tool resources (ports, editor instances). Typical: 2–4 lanes.
- **Task branch:** short-lived, one per task, named `<lane>/<task-slug>`, always created from the
  latest integration branch. Deleted once merged. No long-lived lane branch exists.
- **Integration branch:** where finished work lands; `main` by default. In local mode no folder keeps
  it checked out (git refuses to fast-forward a branch checked out elsewhere).
- **Between tasks** a lane worktree sits on a detached HEAD at the integration branch. Lane names
  are never branch names themselves: git can't have both a branch `ui` and branches `ui/<task>`.

### Configuration (`.claude/kit.toml`)

```toml
[project]
name = "hello-lanes"
test_command = "python -m pytest -q"
integration_branch = "main"
merge_mode = "pr"                      # "pr" (default) or "local"           [12]
worktree_root = ".claude/worktrees"    # or "../{project}-lanes" (Unity)    [2]
ownership = "ask"                      # out-of-lane edit: "ask" (a permission prompt) or "off"
shared_paths = ["docs/changelog.d/**", "docs/backlog/**", "docs/plans/**",
                "docs/design/decisions-log.md", "docs/health/**"]

[[lanes]]
name = "core"
scope = "Domain logic and its tests"
owns = ["src/core/**", "tests/core/**"]
resources = { dev_port = 8001 }

[[lanes]]
name = "api"
scope = "HTTP layer"
owns = ["src/api/**", "tests/api/**"]
resources = { dev_port = 8002 }
```

`resources` is free-form: the lane router tells the agent each value, and packs give some of them
meaning (e.g. the Unity pack's `unity_editor`, `mcp_port`).

### Commands (`kit lanes ...`), all usable by a human or an agent

| Command | Does |
| --- | --- |
| `create [lane...]` | Worktree per lane under `worktree_root`, detached at the integration branch; copies `.worktreeinclude` files |
| `status` | Every lane: folder, current branch, ahead/behind integration, changed and untracked files (counted apart, decision 52), unpushed commits, PR state |
| `start <task>` | Prove the lane's previous task branch merged: its tip is in the integration tip (PR mode fetches first), or `gh` shows a PR merged into the integration branch whose head commit is that tip or contains it (squash merges; a PR found by name alone never counts, decisions 46, 53) → delete it → create `<lane>/<task>` with no upstream from the integration tip (`origin/<integration>` in PR mode, the local `<integration>` in local mode). Refuses with uncommitted changes to tracked files (untracked ones are listed, decision 52), commits on no branch, an open or closed PR, or no `gh`; `--abandon` drops an unmerged previous branch on purpose and prints its SHA |
| `sync` | Bring the integration branch into the task branch: rebase if the branch was never pushed, merge if it was (never force-push a branch under review). A conflict is left in progress with the files and the continue/abort commands (decision 48) |
| `finish` | `sync`, then run `test_command` through the shell (no skip flag) → **PR mode:** push the task branch and open a PR (`--title`, `--body-file`, or `--body-file -` for stdin, which `/wrap-up` uses for the plan link and the review report [65]); a re-run with an open PR only pushes; **local mode:** no network; fast-forward the local integration branch with `git push . HEAD:<integration>`, re-syncing, re-testing and retrying once if another lane moved it meanwhile (any other refusal is reported), then detach and delete the branch. The tests must leave HEAD, the branch and tracked files as they were (decision 49) |
| `remove <lane>` | Remove the worktree (refuses with uncommitted changes, or ignored files that may hold work unless `--force`, decision 45) |

`start`, `sync` and `finish` (plan 05, `kitlib/lane_cycle.py`, merge proof in `lane_merged.py`, PR opening in `lane_pr.py`) run only inside a lane
folder (decision 51). `create`, `status` and `remove` (plan 04, `kitlib/lane_setup.py` and `lane_status.py`) work from any
folder of the repository: the main checkout is found from git (decision 37), and a folder is a lane
when its git top level is `<main>/<worktree_root>/<name>`. They need git 2.36 or newer. Nested lanes get `claudeMdExcludes` for the main
checkout's instruction files in their `settings.local.json` (decision 35).

### Drift is prevented, then detected

- *Prevented:* task branches live for one task, so they can't fall behind or keep stale history.
- *Detected:* the **lane-router hook** (SessionStart: startup, resume, clear, compact) tells the agent
  its lane, scope, owned paths, resources and branch, and warns when the branch is behind, already
  merged, or isn't a task branch. It uses only local git data (no network) and never blocks.
  It works out the lane from the hook input's `cwd`, not `CLAUDE_PROJECT_DIR`.

### Ownership

A PreToolUse hook (`kit hook ownership`) on Edit, Write, MultiEdit and NotebookEdit compares the
file with the lane's `owns` plus `shared_paths` (default: changelog fragments, backlog, plans). It
fails open (decision 41). From a lane, edits to the main checkout or another lane's folder ask too (decision 44). With
`ownership = "ask"` an out-of-lane edit becomes a permission prompt with the reason shown
(`permissionDecision: "ask"`), so a human decides. Ownership reduces conflicts; it isn't security.

### Relation to Claude Code's own features [20]

Lane worktrees sit in the same folder `claude --worktree` uses, so the layout is familiar; they are
ordinary git worktrees, not ones Claude Code created and manages itself. Lanes are
for persistent, human-supervised workstreams; agent teams are for fanning one task out. A lane
session can still use agent teams or `isolation: worktree` subagents inside its task.

## 7. Checks

### One module, three entry points [14]

```
kitlib (config, glob matching, comment stripping, reporting)
   ├── rules_check       ─┐
   ├── protected_paths    ├─  each exposes: check(paths or command) → findings
   └── ownership         ─┘
          │
          ├── hook mode:   kit hook <name>        reads Claude Code JSON on stdin, answers in hook protocol
          ├── CLI mode:    kit check <name> [--staged | --diff BASE | FILES]   exit 0 clean, 1 findings
          └── git mode:    .githooks/pre-commit → kit check all --staged       (opt-in; sets core.hooksPath)
CI runs:   kit check all --diff origin/main
```

### Rules-check (PostToolUse on Edit|Write; also CLI, pre-commit, CI)

```toml
[[checks.rules]]
id = "no-print"
pattern = '\bprint\('
paths = ["src/**/*.py"]
message = "Use the logger, not print()."
```

Comments are stripped by file type before matching. Hook mode exits 2 with the findings on stderr so
Claude fixes the file. **Fails open:** a broken config or crash never blocks an edit; it reports the
problem instead. [9]

### Protected paths and commands

```toml
[protected]
paths = ["vendor/**", "docs/originals/"]
commands = ["git push --force", "git push -f", "git reset --hard", "git clean -f",
            "git commit --no-verify", "git commit -n"]          # defaults when the key is absent
secrets = [".env", ".env.*", "!.env.example"]                 # defaults when the key is absent
guard_kit = true
```

- **Primary:** `kit settings sync` writes deny rules into `settings.json`: `Edit(/<path>)` per
  protected path (root-anchored, which in project settings anchors at the session's working
  directory: the worktree in a lane), `Read(...)` and `Edit(...)` per secret, `Bash(<cmd> *)` and
  `PowerShell(<cmd> *)` per command; plus **ask** rules for the kit's own config when `guard_kit`,
  which prompt in every mode, `bypassPermissions` included [30, 92]. A secret written `!name`
  becomes an exemption rule, kept in `kit.toml`'s order around the bare names it cancels: Claude
  Code carves a `!` rule only out of the unanchored rules listed before it [82, 92]. It records what it wrote in
  `.claude/kit/generated-rules.json` and never touches other rules beyond
  their position around an exemption [29]. `kit check settings` (part of `check all`) reports missing, stale and misplaced
  rules. Every path rule is `Read(...)` or `Edit(...)`: Claude Code consults no other.
- **Backstop:** `kit hook protected`, a PreToolUse hook on Bash, PowerShell and the file tools. It
  matches commands with flags in any order, past `git -C`, wrappers and flag clusters [28]; checks
  file-tool paths; checks the targets of common file commands and PowerShell cmdlets, best effort
  (`kitlib/file_commands.py`) [27]; in `bypassPermissions`, blocks shell writes to the kit's
  config, which its `Edit` ask rules aren't documented to cover [92]; and blocks the agent
  switching the local checks off [34].
  Where it overlaps the deny rules (file tools, recognized shell file commands) it is a **drift
  guard**: it still protects when `settings.json` is stale, and covers PowerShell cmdlets, which
  the docs don't say deny rules cover [92]. **Fails closed:** in PreToolUse only exit 2
  blocks, so every error, a broken `kit.toml`, bad input and a mistyped hook name all exit 2 [33].
- **Pre-commit and CI:** `kit check protected` reports changed protected paths and added secret
  files; `KIT_ALLOW_PROTECTED=1` lets a human commit an intended change [32].
- **Stated limits** (`docs/ai/protected-paths.md` in each project): none of this stops a script that
  opens files itself. The OS-level answer is Claude Code's sandbox, which runs on macOS, Linux and
  WSL2 but **not native Windows**; the server-side answer is CI, branch protection and `CODEOWNERS`.
  [15]

## 8. Shared docs without merge conflicts [13]

| Doc | How lanes write to it |
| --- | --- |
| `docs/changelog.d/<lane>-<task>.md` | one fragment per task branch; `kit changelog build` compiles them into `CHANGELOG.md` at release |
| `docs/backlog/<slug>.md` | one file per item with a header (`status`, `lane`, `size`); done = file moves to `docs/backlog/done/` |
| `docs/plans/YYYY-MM-DD-slug.md` | one file per plan, named by date and slug (no shared counter, no index table); `/next` reads each plan's status line |
| `docs/BUILD-STATE.md` | regenerated by a skill; on conflict take either side and regenerate |
| `docs/design/decisions-log.md` | newest-first entries; a lane adds at most one entry per task (small conflict surface, kept as one file for readability) |

## 9. Skills and the reviewer

| Skill | Model | Does | Calls |
| --- | --- | --- | --- |
| `/onboard` (08) | opus | Reads the repo after install; proposes stack facts, test command, rules files, lanes, at most three `P` checks; writes on approval [68] | `kit check settings`, `kit settings sync`, `kit lanes create` |
| `/plan-feature` | opus | Understand → ask → task branch → plan file (Draft) → stop for approval | `kit lanes start` (outside a lane: `git switch`) |
| `/implement` | sonnet | Build one approved plan, tests first, on its branch; stop on anything the plan doesn't settle | `kit next` |
| `/wrap-up` | sonnet | Tests → reviewer → docs and fragment → commit message → finish on OK; for each thing corrected more than once, proposes one rules line, `P` check or `kit.toml` pattern (never adds it unasked) [66] | `kit lanes finish` (outside a lane: `git push`, `gh pr create`) |
| `/code-health` (07b) | opus | Whole-codebase audit by area (parallel `sonnet` subagents) against the project's rules → findings → dated report and chosen backlog items on a `health-<date>-<area>` branch; changes no code; not a diff review (built-in `/code-review`) [86] [87] [88] | `kit lanes start` (outside a lane: `git switch`) |
| `/design` (07b) | opus | Read one design-doc section → options and a recommendation → on OK, the exact `DESIGN.md` edit and a decisions-log entry; changes no branches [89] | — |
| `/next` | sonnet | Read-only: ready / waiting on you / blocked, per lane; ends with one recommended prompt. Prototyped as this repo's own `/kit-next` [26] [64] | `kit next` [63] |

Every skill's step 0 is the lane check: `kit next`'s first line says lane, main checkout (or another
worktree that isn't a lane) or not a lane (no lanes), and the skill handles each [62]. Skills run the kit as
`sh .claude/kit/kit <command>`, a launcher that takes Python from `python-path`, because a
kit-owned file can't hold `{{kit_command}}` or an interpreter path [71]. Skills with side effects
set `disable-model-invocation: true`, and `allowed-tools` pre-approves only read-only commands, so
commits and pushes still prompt [67]. Model names use aliases (`opus`, `sonnet`), not dated IDs;
`model` applies when the owner types `/name` (seen live, plan 07). Skills: `payload/kit-owned/.claude/skills/`.

**Reviewer** (`.claude/agents/reviewer.md`, model `opus`): fresh context, with `CLAUDE.md` and
`AGENTS.md` loaded; reads the branch's diff against the merge base (plus uncommitted and new files),
`CODE-STANDARDS.md`, the rules files matching changed paths, the plan, and **every** `*.md` in
`.claude/review/`: `universal.md` (kit-owned, `U1`…), `project.md` (project-owned, `P1`…) and one
file per pack (its own prefix, declared in the first line) [54] [55]. Judges only changed lines;
at most three pre-existing problems, without severity [56]. Report: verdict, findings citing a
check ID with 🔴 fix now / 🟠 fix soon / 🟡 polish, checks run, outside this change; an unsettled
design question is "needs the owner" [58]. **Read-only by enforcement** [57]: `tools: Read, Grep,
Glob, Bash`, and a `PreToolUse` hook in its own frontmatter runs `sh
"$CLAUDE_PROJECT_DIR/.claude/kit/hook" reviewer-bash`, which allows only read-only git (every command in a
chain; `cd <folder>` too; no redirects, substitutions or globs outside quotes; plain `git`, no path)
and fails closed, timeout 30 s. `.claude/kit/hook` is a launcher that takes Python
from `.claude/kit/python-path`, because a kit-owned file can't hold a machine's interpreter path.

## 10. Installer and onboarding [17] [19]

```
install.ps1 / install.sh
  └─ check git, Python ≥ 3.11 (real interpreter, not the Windows Store alias), Claude Code, gh (optional)
     └─ kit_setup.py [--dry-run] [--target DIR] [--pack unity]
          1. detect: new folder or existing repo; existing CLAUDE.md / AGENTS.md / .claude/
          2. ask only what can't be detected (name, one-line description, lanes, packs)
          3. plan the file list; --dry-run prints it and stops
          4. existing file → ask: skip / keep both (writes .kit-new beside it) / overwrite
          5. copy kit-owned, render templates, write manifest, write hook commands with the
             interpreter's full path (quoted: paths with spaces)
          6. print next steps: open Claude Code, run /onboard
/onboard (agentic): stack, test command, rules files, lane split → owner approves → written
```

## 11. Packs

A pack is a folder with `pack.toml` (name, description, what it adds), `kit-owned/`, `templates/`,
optional `kit.toml` fragments (checks, protected paths, lane resources), `settings` fragments
(permissions), and a reviewer checklist (`.claude/review/<pack>.md`). The installer merges fragments; the format doc (plan 10)
is the contract for new packs. First pack: Unity (sibling-folder worktrees, per-lane editor + MCP
instance, Unity ignores and attributes, reviewer items, pattern rules, test command).

## 12. Distribution

- **Now:** GitHub template repository plus the installer (works on existing repos too).
- **Later:** a Claude Code plugin built from `payload/kit-owned/` (skills, agents, `hooks/hooks.json`
  using `${CLAUDE_PLUGIN_ROOT}`). Project-owned templates still come from `kit_setup.py` or `/onboard`.
- Semantic versioning; `CHANGELOG.md` in this repo; the installed version is in `.claude/kit/VERSION`.

## 13. Testing

| Level | What | Where | When |
| --- | --- | --- | --- |
| Unit | kitlib, each check, config parsing, command normalization | `tests/` | every push (Windows + Ubuntu, Python 3.11 + 3.13) |
| Integration | lanes commands on throwaway git repos (with a bare repo as `origin`); installer into temp folders, including paths with spaces | `tests/` | every push |
| Hook protocol | feed recorded Claude Code hook JSON on stdin; assert exit codes and output | `tests/` | every push |
| Evals | `claude -p --output-format stream-json` sessions on the example project, with pinned settings and asserting what loaded (decision 93): reviewer finds a planted bug, backstop blocks a force-push, `/next` reports correctly | `evals/` | on demand / nightly (plan 11 decides) |
| Live checks (kit dev only) | `tests/live/`, through `claude_run.py`: Claude Code runs the kit as assumed (decision 93) | `tests/live/` | on demand, `pytest --live` |

## 14. Platform notes (Windows first)

- Python: `python` may be the Microsoft Store alias; `python3` usually doesn't exist on Windows. The
  installer resolves a real interpreter and writes its full path. [19]
- Paths with spaces everywhere (e.g. `D:\My Projects\...`): quote every path in hook commands;
  tests cover it.
- Files the kit writes are written with LF endings explicitly (Python's text mode on Windows
  writes CRLF).
- Line endings: `.gitattributes` forces LF in the repo; `.ps1` keeps CRLF.
- Permission patterns are matched in POSIX form (`C:\x` → `/c/x`).
- The sandbox isn't available on native Windows (see §7).

## 15. Open questions

| Question | Answered by |
| --- | --- |
| ~~Which shell runs hook commands on native Windows?~~ Answered in plan 02: Git Bash by default, PowerShell if it's missing; the `args` form runs the program with no shell, avoiding quoting problems. Plan 08 uses `args` | plan 08 |
| ~~Does `CLAUDE_PROJECT_DIR` point at the worktree or the main checkout in a lane session?~~ Moot: the lane hooks use the hook input's `cwd` (verified live in plan 04). In the agent's own shell it is not set at all; it exists only for hook processes | — |
| Shim (`kit`, `kit.cmd`) vs `python .claude/kit/cli.py`: is a root-level shim acceptable in every project? A bare `kit` needs PATH or `./kit`; templates use `{{kit_command}}`, so the answer only sets that value | plan 08 |
| `claude plugin eval` vs a hand-written `evals/run.py`: the page is published, and plugin eval loads no project `.claude/` or `CLAUDE.md`, so plan 11 keeps its own `claude -p` harness and borrows plugin eval's design (decision 80, `survey-claude-code.md`) | plan 11 |
| ~~`/next` must skip the `README.md` and `_TEMPLATE.md` beside backlog items~~ Answered: `kit next` skips them, `done/` and `finished/` (decision 63) | — |
| ~~Kit-owned skills under `payload/` discovered while developing the kit?~~ Yes, verified live in plan 07 (Claude Code 2.1.284): they load once a file under `payload/kit-owned/` is read; a name clashing with a root skill is listed as `/payload/kit-owned:next` (the root one wins `/next`), others under their plain names. This repo's prototype is now `/kit-next` (decision 64), and a test keeps the names apart. Also seen: a skill's `model` took effect when typed as `/name`, but not when Claude ran it through the Skill tool (one headless run each) | — |
| ~~Pre-commit mechanism~~ Answered: native `.githooks`, enabled after asking (decision 25); pre-commit framework support is Later | — |
| Values rendered into `kit.toml` must be TOML-escaped (a test command containing `"` would break it) | plan 08 |
| ~~Worktrees nested in the main checkout load the root's `CLAUDE.md`?~~ Yes (instruction files load from every folder up to the root). Plan 04: `lanes create` adds `claudeMdExcludes` to the lane's `settings.local.json` (decision 35); verified live on Windows with forward-slash absolute paths containing a space: the session's loaded-instructions list had the main checkout's `CLAUDE.local.md` (not excluded) but not its `CLAUDE.md` in the same folder. Checked again on Linux (WSL2) and Windows with Claude Code 2.1.291 (decision 84): a lane loads neither of the main checkout's committed `CLAUDE.md` nor `.claude/CLAUDE.md` even without excludes, so they are now a backstop; it does load the main checkout's `CLAUDE.local.md`; the lane's own `settings.local.json` works on both, and on Linux the main checkout's applies too. Not shown: the `AGENTS.md` entry on its own, macOS. Root tools must skip `.claude/worktrees/` (documented in `parallel-lanes.md`) | — |
| ~~What the main checkout holds~~ Answered (decision 38): whatever the owner left; `lanes status` warns in local mode when it has the integration branch checked out | — |
| ~~PR-mode merge detection~~ Answered in plan 05 (decision 46): `lanes start` counts only a merged PR whose head commit is the branch tip; open, closed or no PR refuses, `--abandon` drops the branch on purpose | — |
| ~~Claude Code's auto memory across worktrees~~ Verified live on Windows (plan 04): a lane uses the main checkout's memory folder, so every lane shares one memory. Documented in `parallel-lanes.md`; lane-aware memory is on the roadmap as Later | — |
| Live-verify what plan 03's live run didn't cover: deny rules written by `kit settings sync`, the Edit/MultiEdit/NotebookEdit tools, fail-closed with a broken config, macOS/Linux. The hook itself was verified live on Windows (Bash, PowerShell, Write; auto mode); the ask rules in `acceptEdits` and `bypassPermissions` were checked live (decision 92) | plan 08 |
| ~~Do ask rules still prompt in `acceptEdits` mode?~~ Answered (decision 92): ask rules are never auto-approved, in `acceptEdits` or `bypassPermissions`; the hook's bypass-mode block now covers shell commands only. Open: the same gap in `acceptEdits`, `auto`, `dontAsk` and allow-listed commands (backlog `kit-config-shell-guard-modes`). Not live-checked: whether `Edit` ask rules cover `rm`, redirections or PowerShell cmdlets | — |
| Wire `kit hook protected` as PreToolUse with matcher `Bash\|PowerShell\|Edit\|Write\|MultiEdit\|NotebookEdit`, run `kit settings sync` at install, commit `.claude/kit/generated-rules.json` (or fold it into the manifest, decision 29) | plan 08 |
| Wire `kit hook lane-router` (SessionStart, no matcher) and `kit hook ownership` (PreToolUse, matcher `Edit\|Write\|MultiEdit\|NotebookEdit`) into `settings.json` at install; plan 04 verified both live via a lane's `settings.local.json`. Not yet live-verified: `bypassPermissions` and `acceptEdits` behaviour of the ownership `ask`, macOS/Linux | plan 08 |
| Plan 05 was live-checked by a script against a real GitHub repo (Windows); plan 07 drove `lanes start`/`finish` through the skills in headless sessions (local mode, and PR mode against a local origin with a stand-in `gh`). Not yet shown live: the skills opening a real GitHub PR, a project without lanes, a sync conflict during `/wrap-up`, macOS/Linux, merge-commit merges, and GitHub's "Update branch" followed by a squash merge (both unit-tested) | plan 11 |
| The reviewer's read-only guard (a hook in the agent's frontmatter) **is skipped in a folder Claude Code doesn't trust**, while the agent still runs with Bash; only the debug log says so (found live in plan 06). The installer's next steps must have the owner open Claude Code in the project once and accept the trust dialog; evals (plan 11) must trust their folder first | plans 08, 11 |
| The guard runs `sh .claude/kit/hook`: if Claude Code runs hooks through PowerShell (Windows without Git Bash), `sh` is missing, the hook exits non-2 and the guard fails open. The installer requires Git Bash or gives the agent a PowerShell launcher; it also writes `.claude/kit/python-path`. A hook timeout (30 s) also lets the call through. Not live-verified: macOS/Linux | plan 08 |
| ~~Does `/wrap-up` propose a `P` check or a rules line after the same correction twice?~~ Answered: one of a rules line, a `P` check or a `kit.toml` pattern, on a yes (decision 66). `/onboard` proposes at most three `P` checks (decision 68) | plan 08 |
| The installer writes and gitignores `.claude/kit/python-path`, which the skills' `kit` launcher needs as the hook launcher does; `.worktreeinclude` copies it into each lane (found in plan 07's live run) | plan 08 |
| Generate `CODEOWNERS` entries from `[protected].paths`, document branch protection (required review, no force pushes), and decide how a PR declares an intended protected change (label, trailer) | plan 09 |

## References

- Permissions (path anchoring, what deny rules cover): https://code.claude.com/docs/en/permissions
- Sandboxing (platforms, scope): https://code.claude.com/docs/en/sandboxing
- Hooks: https://code.claude.com/docs/en/hooks
- Skills: https://code.claude.com/docs/en/skills
- Subagents: https://code.claude.com/docs/en/sub-agents
- Memory, rules, `@` imports, AGENTS.md: https://code.claude.com/docs/en/memory
- Worktrees: https://code.claude.com/docs/en/worktrees
- Plugins: https://code.claude.com/docs/en/plugins
- Headless mode: https://code.claude.com/docs/en/headless
