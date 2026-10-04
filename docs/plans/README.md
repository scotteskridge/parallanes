# Plans

The kit is built as a numbered series of plans. Each plan is one branch (`plan/NN-short-name`) and
one pull request, which links the plan and carries the reviewer's report. Format: `_TEMPLATE.md`.
Design they build on: `../ARCHITECTURE.md`.

| # | Plan | Scope | Status |
| --- | --- | --- | --- |
| 00 | [Architecture and plan series](00-architecture.md) | `ARCHITECTURE.md`, this index, plan template, roadmap and decisions updates | Done |
| 01 | [Instruction templates](01-instruction-templates.md) | `AGENTS.md` / `CLAUDE.md` / `.claude/rules/` templates, docs scaffolding, changelog and backlog fragments, placeholder rendering | Draft |
| 02 | Check library + rules-check | Shared `kitlib` (`kit.toml` loading, globs, comment stripping, reporting); the `kit` CLI with `changelog build`; rules-check as hook, CLI and pre-commit | Not started |
| 03 | Protected paths | `settings.json` deny rules (primary), protected-paths hook (backstop), sandbox guidance, honest limits | Not started |
| 04 | Lanes core | `[[lanes]]` in `.claude/kit.toml`, `lanes create`, `lanes status`, lane-router hook with drift checks, ownership check | Not started |
| 05 | Lane task cycle | `lanes start`, `lanes finish`, `lanes sync`; PR mode and local mode | Not started |
| 06 | Reviewer | `reviewer` subagent, universal checklist, stack checklist mechanism | Not started |
| 07 | Skills | `/plan-feature`, `/implement`, `/wrap-up`, `/code-health`, `/design`, `/next`, `/onboard` and their templates | Not started |
| 08 | Installer | `install.ps1` / `install.sh` → `kit_setup.py`: prerequisites, interpreter detection, dry run, manifest, no overwrites | Not started |
| 09 | CI template | GitHub Actions workflow for installed projects: tests + rules-check + protected-path check on every push and PR | Not started |
| 10 | Unity pack | Pack format docs + Unity pack (ignores, MCP, per-lane editors, reviewer items, patterns, sibling-folder worktrees) | Not started |
| 11 | Example project + evals | Small Python project set up with the kit; `claude -p` scenario tests | Not started |
| 12 | Launch | README, architecture diagram, guardrail table, template repo, v0.1.0, make public | Not started |

Order: checks and lanes (02–05) come before skills (07), so skills are written against commands that
already exist. The installer (08) comes once there is something to install.
