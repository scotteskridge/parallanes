# claude-code-lanes-starter

> **Work in progress.** Building toward v0.1.0. See [docs/ROADMAP.md](docs/ROADMAP.md).

A starter kit that sets up any project for disciplined AI-agent development with
[Claude Code](https://code.claude.com): short instructions the agent actually follows, slash-command
workflows (plan → implement → wrap up), a fresh-context reviewer, hooks that enforce the rules
automatically, and **parallel lanes**: several agents working at once, each in its own git worktree,
merging into a shared branch only after tests pass.

Generalized from a real project, a Unity game built across three parallel agent lanes
([survey](docs/survey-hoem.md)). Design decisions are recorded in
[docs/decisions-log.md](docs/decisions-log.md).

## Status

Built as a numbered series of plans, one pull request each: [docs/plans/README.md](docs/plans/README.md).
The design they build against: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

| Piece | Plan | State |
| --- | --- | --- |
| Architecture and plan series | 00 | ✅ done |
| Instruction templates | 01 | ✅ done |
| Check library, `kit` CLI, rules-check (hook + CLI + pre-commit) | 02 | ✅ done |
| Protected paths (deny rules + command backstop) | 03 | ✅ done |
| Lanes core: config, create, status, remove, lane-router and ownership hooks | 04 | ✅ done |
| Lane task cycle: start, sync, finish (PR and local mode) | 05 | ✅ done |
| Reviewer: read-only subagent, numbered checklists (universal, project, stack) | 06 | ✅ done |
| Skills: the task loop (`/next`, `/plan-feature`, `/implement`, `/wrap-up`) and `kit next` | 07 | ✅ done |
| Skills: `/design`, `/code-health`, `/onboard` | 07b | planned |
| Installer (Windows first) and CI template | 08–09 | planned |
| Unity pack | 10 | planned |
| Example Python project and evals | 11 | planned |

## License

[MIT](LICENSE)
