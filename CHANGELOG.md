# Changelog

All notable changes to the kit. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- A backlog for the kit itself (`docs/backlog/`, the format the kit installs), seeded with eight
  items from a code review: lint, format, type hints and type checking, coverage, the test command in
  `AGENTS.md`, decision-number comments, and the weight of the plan process. Five more from a
  comparison with Claude Code's built-in features: shipping the kit-owned parts as a plugin, a
  plugin name that passes validation, lanes with `claude --worktree`, a two-lane trial on a real
  non-Unity project, and a README table of what the kit adds.
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
