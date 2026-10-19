@AGENTS.md

## Claude Code specifics
- This repo builds a Claude Code kit. For questions about Claude Code features (hooks, skills,
  subagents, settings, plugins, worktrees), check the current docs or the `claude-code-guide` agent;
  don't answer from memory.
- Never run a payload skill (/next, /plan-feature, /implement, /wrap-up) in this repo; they load
  here once a payload file is read. This repo's own status skill is `/kit-next`.
- Changes to this file or `AGENTS.md`: propose the exact lines and wait for an OK. Keep this file
  under ~100 lines.
- **Standing permission to push and merge (owner, 2026-10-07):** push any branch except `main`
  without asking. Merge a PR with `gh pr merge --merge --delete-branch` once the owner has said
  in chat that it's approved and the full suite and both ruff commands passed locally on the
  pushed commit; CI need not finish first (decision 118). Report CI's result when it lands and fix
  a red run with a follow-up PR. Never push to `main` directly, force-push, or merge a PR the
  owner hasn't approved.
- When compacting, keep: the task, the approved plan, files changed, latest test results, open
  questions.
