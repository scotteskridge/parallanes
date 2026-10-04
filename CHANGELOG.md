# Changelog

All notable changes to the kit. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
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
