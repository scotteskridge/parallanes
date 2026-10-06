@AGENTS.md

## Claude Code specifics
- This repo builds a Claude Code kit. For questions about Claude Code features (hooks, skills,
  subagents, settings, plugins, worktrees), check the current docs or the `claude-code-guide` agent;
  don't answer from memory.
- Never run a payload skill (/next, /plan-feature, /implement, /wrap-up) in this repo; they load
  here once a payload file is read. This repo's own status skill is `/kit-next`.
- Changes to this file or `AGENTS.md`: propose the exact lines and wait for an OK. Keep this file
  under ~100 lines.
- When compacting, keep: the task, the approved plan, files changed, latest test results, open
  questions.
