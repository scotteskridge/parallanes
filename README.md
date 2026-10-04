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

| Piece | State |
| --- | --- |
| Survey of the source setup | ✅ done |
| Instructions, skills, reviewer | planned |
| Hooks (rules-check, protected paths, lane router) | planned |
| Lanes CLI (`create`, `status`, `sync`, `merge`) | planned |
| Setup script (Windows first) | planned |
| Unity pack | planned |
| Example Python project | planned |

## License

[MIT](LICENSE)
