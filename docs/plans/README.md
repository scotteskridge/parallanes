# Plans

The kit is built as a numbered series of plans. Each plan is one branch (`plan/NN-short-name`) and
one pull request, which links the plan and carries the reviewer's report. Format: `_TEMPLATE.md`.
Design they build on: `../ARCHITECTURE.md`.

| # | Plan | Scope | Status |
| --- | --- | --- | --- |
| 00 | [Architecture and plan series](00-architecture.md) | `ARCHITECTURE.md`, this index, plan template, roadmap and decisions updates | Done |
| 01 | [Instruction templates](01-instruction-templates.md) | `AGENTS.md` / `CLAUDE.md` / `.claude/rules/` templates, docs scaffolding, changelog and backlog fragments, placeholder rendering | Done |
| 02 | [Check library + rules-check](02-check-library.md) | Shared `kitlib` (`kit.toml` loading, globs, comment stripping, reporting); the `kit` CLI with `changelog build`; rules-check as hook, CLI and pre-commit | Done |
| 03 | [Protected paths](03-protected-paths.md) | `settings.json` deny rules (primary), protected-paths hook (backstop), sandbox guidance, honest limits | Done |
| 04 | [Lanes core](04-lanes-core.md) | `[[lanes]]` in `.claude/kit.toml`, `lanes create`, `lanes status`, lane-router hook with drift checks, ownership check | Done |
| 05 | [Lane task cycle](05-lane-task-cycle.md) | `lanes start`, `lanes finish`, `lanes sync`; PR mode and local mode | Done |
| 06 | [Reviewer](06-reviewer.md) | `reviewer` subagent, universal checklist, stack checklist mechanism | Done |
| 07 | [Skills: the task loop](07-skills.md) | `/next` (lane- and backlog-aware, with `kit next`; grown from this repo's prototype, decision 26), `/plan-feature`, `/implement`, `/wrap-up` (incl. rule proposals after repeated corrections) | Done |
| 07b | [Skills: design and code health](07b-design-health.md) | `/design`, `/code-health` (dated report, findings become backlog items) (decisions 61, 69, 85–91) | Done |
| 08 | [Installer](08-installer.md) | One `kit init` (behind `install.ps1` / `install.sh`) that copies the kit in: prerequisites, interpreter detection, dry run, manifest, no overwrites (decision 78) | Done |
| 09 | [CI template](09-ci-template.md) | GitHub Actions workflow for installed projects: tests + rules-check + protected-path check on every push and PR | Done |
| 10 | Unity pack | Pack format docs + Unity pack (ignores, MCP, per-lane editors, reviewer items, patterns, sibling-folder worktrees) | v0.2 |
| 11 | Evals | About five `claude -p` scenarios on the trial project (decision 80) | v0.2 |
| 12 | Launch | README (story first, what Claude Code does vs what the kit adds), the trial's real output, rename to `worklanes` (decision 81), template repo, v0.1.0, make public | Not started |

## Build order for v0.1 (decision 77)

Build only what Claude Code doesn't already do: lanes with an enforced task cycle. Steps that
aren't plans are backlog items in [../backlog/](../backlog/); one that needs a plan gets a plan file
like any other.

1. ~~Plan 07: the task-loop skills~~ (done); plan 07b (`/design`, `/code-health`) was built
   alongside, ahead of the v0.2 it was first set for
2. Small fixes, each under an hour: `lane-settings-cross-platform`, `revisit-permission-decisions`,
   `live-checks-pin-what-loads`, `lint-and-format-in-ci`, `agents-md-venv-test-command`
3. ~~The lane-boundary check: `lane-boundary-check`, with `lane-overlap-check` for files two lanes claim~~ (done)
4. ~~Plan 08: the installer~~ (done)
5. A two-lane trial on a small web project: `prove-it-on-a-real-project` (trial done:
   [write-up](../trial/two-lane-trial.md); still open: `lanes-and-worktree-flag` and
   `lane-dependency-hint`)
6. ~~Plan 09: the CI template~~ (done)
7. Plan 12: launch (with `readme-builtins-comparison` and `plugin-name`)

**v0.2:** the plugin (`ship-kit-as-plugin`), `/onboard`, plan 10, plan 11, per-lane ports
(`lane-resources-env`, `lane-session-identity`), and the backlog items marked `later`.

Process (decision 79): at most three open questions per plan, each with Claude's recommended
answer for the owner to approve; small plans get one review round unless it finds a 🔴.
