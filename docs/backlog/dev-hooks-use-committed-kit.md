---
status: idea
lane: any
size: S
---
# Keep the kit repo's own hooks off half-written kit code

While building the kit, this repo's hooks run the kit straight from the main checkout's
`payload/kit-owned/.claude/kit/`. Any session's half-finished edit there therefore changes, or
breaks, the guard for every other session, including ones in other worktrees. On 2026-10-08 one
broken uncommitted file blocked every session in the repo until the owner fixed it by hand (see
[kit-load-error-message](kit-load-error-message.md)).

Installed projects don't have this problem: their hooks run `$CLAUDE_PROJECT_DIR/.claude/kit/hook`,
so each lane uses its own committed copy, and `.claude/kit/` is a protected path.

Likely shape: point the repo's hooks at a copy of the kit taken from `main` (refreshed after each
merge), not at the working tree being edited.

**Done when:** an uncommitted syntax error under `payload/kit-owned/` no longer blocks other
sessions' tool calls in this repo, and the setup is described in `AGENTS.md` (owner's OK needed).
