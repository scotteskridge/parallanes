# Changelog

All notable changes to the kit. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `/design` and `/code-health` (plan 07b), kit-owned. `/design` settles one design question from one
  section of the design docs and, on the owner's OK, records it in `DESIGN.md` and the decisions log.
  `/code-health` audits the whole codebase by area with parallel read-only subagents, writes a dated
  report to `docs/health/`, and turns the findings the owner picks into backlog items. `/onboard`
  moves out of 07b and stays in v0.2 (decisions 77, 85). `docs/health/**` is shared by every lane by default.
- The task-loop skills (plan 07), kit-owned: `/next` (what to work on, from `kit next`), `/plan-feature`
  (task branch and a plan, then stop for approval), `/implement` (test-first, stops on anything the
  plan doesn't settle) and `/wrap-up` (tests, the reviewer, changelog fragment and plan notes, rule
  proposals for repeated corrections, then commit and `lanes finish` on the owner's yes). Each starts
  with a lane check and also works in projects without lanes; only read-only commands are
  pre-approved. Tests check that every `kit` command and path a skill names exists.
- `kit next`: this folder's lane, every lane, open plans by status and backlog items by header, with
  unreadable files listed as problems. `sh .claude/kit/kit`, a launcher skills use to run the kit.
- `lanes finish --body-file -` reads the PR body from stdin, so `/wrap-up` needs no file.
- A backlog for the kit itself (`docs/backlog/`, the format the kit installs), seeded with eight
  items from a code review: lint, format, type hints and type checking, coverage, the test command in
  `AGENTS.md`, decision-number comments, and the weight of the plan process. Five more from a
  comparison with Claude Code's built-in features: shipping the kit-owned parts as a plugin, a
  plugin name that passes validation, lanes with `claude --worktree`, a two-lane trial on a real
  non-Unity project, and a README table of what the kit adds. Six more from studying lanekeeper,
  a tool for the same problem: a lane-boundary check where work lands, modes for shared paths, a
  rule for overlapping lanes, ports in each lane's environment, a fix hint when a boundary stops
  something, and `doctor` plus uninstall.
- `docs/survey-lanekeeper.md`: what to borrow from lanekeeper for each future step, at a pinned
  commit, with the test cases to port and what not to copy (decision 74: build on it, don't
  reinvent it). Three more backlog items from it: an install hint for new lanes, check results on
  the PR page, and CODEOWNERS from the lanes.
- The kit's own tests run in parallel (`pytest-xdist`, `-n auto`): about 5 minutes → 1 on Windows.
- Fast test feedback: a `slow` marker on the git-heavy lane tests, so `python -m pytest -m "not
  slow"` runs 488 tests in ~15 s while working, including unit tests that give every lane module fast coverage. Fixture repos are built once per worker and copied,
  so the full suite takes 80–107 s instead of 135–155 s. CI runs the full suite once per OS and the fast set
  on the other Python versions. `lanes status` lists worktrees once instead of once per lane, and the
  lane commands check for uncommitted and untracked files with one `git status`.
- Repository skeleton: license, roadmap, decisions log, survey of the source setup, CI running pytest
  on Windows and Ubuntu.
- Architecture document, plan template and the numbered plan series (plan 00); decisions 10–20
  from a best-practice review: one short-lived branch per task, PR-mode merges, conflict-free
  changelog fragments and backlog files, checks with hook/CLI/pre-commit entry points, evals.
- Project templates (plan 01): `AGENTS.md`, `CLAUDE.md`, path-scoped rules for tests and design
  docs, human guides (`WORKFLOW.md`, `parallel-lanes.md`), plans, one-file-per-item backlog,
  changelog fragments, code standards, design docs, git files; a placeholder registry and a
  strict renderer that fails on unknown or missing placeholders.
- The `kit` CLI and check library (plan 02): forbidden-pattern rules in `.claude/kit.toml`,
  enforced as a Claude Code PostToolUse hook, by `kit check` (files, `--staged`, `--diff BASE`),
  and by a git pre-commit hook; strict config validation; `kit changelog build` compiles
  fragments into a release section.
- Protected paths and commands (plan 03): `[protected]` in `.claude/kit.toml` (paths, commands,
  secrets, guard for the kit's own config). `kit settings sync` writes the matching deny and ask
  rules into `settings.json` and `kit check settings` reports drift; `kit hook protected`, a
  PreToolUse backstop that fails closed, catches command forms deny rules miss, file-command and
  PowerShell writes, and the agent switching checks off; `kit check protected` reports protected
  changes in pre-commit and CI. Each project gets a doc stating what this does not stop.
- Lanes core (plan 04): `[[lanes]]` in `.claude/kit.toml`, validated strictly; `kit lanes create`
  (a worktree per lane, detached at the integration tip, `.worktreeinclude` files copied, the main
  checkout's `CLAUDE.md` excluded from nested lanes), `kit lanes status` (branch, ahead/behind,
  uncommitted, unpushed, PR state via `gh`, overlap notes, local-mode warning about the main
  checkout) and `kit lanes remove`; `kit hook lane-router` (SessionStart briefing with drift
  warnings) and `kit hook ownership` (out-of-lane edits ask the user). Hook handlers moved from
  `cli.py` to `kitlib/hooks.py`.
- Lane task cycle (plan 05): `kit lanes start <task>` (a fresh `<lane>/<task>` branch with no
  upstream, only once the previous one is proved merged: by ancestry, or in PR mode by a merged PR
  at the branch's exact head commit; `--abandon` otherwise), `kit lanes sync` (rebase if never
  pushed, merge if pushed, conflicts left for the agent to resolve) and `kit lanes finish` (sync,
  run `test_command`, then push and open a PR, or fast-forward the integration branch in local
  mode with one retry if another lane landed first). Only tracked changes block them; untracked
  files are listed. `lanes status` now matches PRs by commit, not branch name, and says when a
  pushed branch is gone from origin. The `lanes` handler moved to `kitlib/lane_cli.py`.
- Reviewer (plan 06): a `reviewer` subagent (opus, fresh context) that reviews only the current
  change against the plan, the project's rules and numbered checklists in `.claude/review/`
  (`universal.md` U1–U15, the project's own `project.md`, one file per stack pack), and returns one
  fixed report: verdict, findings with check IDs and 🔴/🟠/🟡, checks run. It is read-only by
  enforcement: read tools only, and `kit hook reviewer-bash` (fail closed, run from the agent's
  frontmatter through the `.claude/kit/hook` launcher) lets Bash run only read-only git. This repo
  now reviews its own plans with copies of the reviewer that a test keeps equal to the payload.
- `/next` for developing this repo: where the build stands and one recommended prompt
  (read-only; prototype for plan 07's installable `/next`).
- `docs/survey-claude-code.md`: what Claude Code's own features already do or constrain, by plan,
  with the decisions they contradict (30, 31, 35, 57) for the owner to revisit, and six backlog
  items: lane settings on macOS/Linux, the permission decisions, lane session names and ports
  through built-in hooks, pinning what live checks load, hook `if` conditions, and `REVIEW.md`.

### Changed
- Permission defaults follow Claude Code's current docs (decisions 82, 92). Secrets default to
  `.env` and every `.env.*` except `.env.example`, through a `!` exemption that the deny rules, the
  hook and the pre-commit check all honour; an exemption Claude Code would ignore is a config
  error. `kit settings sync` keeps exemptions in `kit.toml`'s order, and `kit check settings`
  reports one out of order. The hook no longer blocks file-tool edits to kit config in
  `bypassPermissions` mode: a live check showed the ask rules are never auto-approved there or in
  `acceptEdits`. It still blocks shell writes to kit config in bypass mode. `protected-paths.md` names the Windows options for a real boundary
  (WSL2, a container, a VM).
- Lane instructions checked live on Linux (WSL2) and Windows (decision 84): no bug. A lane's own
  `settings.local.json` works on both. Claude Code 2.1.291 already keeps the main checkout's
  committed instructions out of a lane, so the kit's excludes are now a backstop.
- A plan for v0.1 (decisions 77–82): a small kit that works first, built only where Claude Code
  has no built-in. Seven steps in `docs/plans/README.md`. The plugin, plan 07b, the Unity pack,
  evals and per-lane ports move to v0.2. The installer copies files for now. Process gets lighter
  (at most three open questions per plan, each with a recommended answer). The secrets default
  is to become `.env.*` with an `.env.example` exemption, in the fix batch. The backlog statuses follow the plan, and
  `/kit-next` follows the build order.
- `docs/design/decisions-log.md` is shared by every lane by default; new lanes get the machine's
  `.claude/kit/python-path` through `.worktreeinclude`. This repo's own `/next` is now `/kit-next`.
- `lanes status` and the lane router's warning count changed and untracked files apart ("N changed ·
  N untracked" instead of "N uncommitted"): only changed tracked files are unfinished work.
- A backlog item's `blocked_by` may name a plan (done once it is in `docs/plans/finished/`); a
  blocker that names nothing, or the item itself, is reported by `kit next`.
- The kit's name is `worklanes` (decision 73): `claude-` plugin names are reserved, and
  `laneguard` read too much like the existing `lanekeeper`.
