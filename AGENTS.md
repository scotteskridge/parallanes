# claude-code-lanes-starter: rules for any coding agent

A starter kit that sets up a project for AI-agent development: instructions, skills, a reviewer
subagent, enforcement hooks, and **parallel lanes** (several agents at once, one git worktree each).
This repo builds the kit; the files it installs into other projects live under `kit/`, `templates/`
and `packs/` (once they exist). Plan and status: `docs/ROADMAP.md`. Why things are the way they are:
`docs/decisions-log.md`.

## Stack
- Python 3.11+, **standard library only** in anything that gets installed into a project (hooks,
  lanes CLI, setup). Dev-only tools (pytest) are fine for the kit's own tests.
- Windows first (PowerShell, paths with spaces, CRLF), then macOS/Linux. CI runs both.
- The shell starts at the project root: never prefix commands with `cd`.

## Checking your work
- Run `python -m pytest` and report the result lines. Evidence, not claims.
- Every hook and CLI command has tests. Test paths with spaces and Windows separators.
- **Never weaken, skip or delete a test, or swallow an exception, to make something pass.** Fix the
  cause or stop and say so.

## Hard rules
- **Search before you create:** extend what exists and say what you found.
- **Never hide errors.** Fail loudly on impossible states. The one deliberate exception: hooks that are
  documented to fail open (see `docs/decisions-log.md`).
- **Stay in scope:** one task per session. List follow-up ideas at the end instead of doing them.
- **Flag undecided design questions** instead of settling them silently; record settled ones at the
  top of `docs/decisions-log.md`.
- Never overwrite a user's existing file from the installer without asking.
- No secrets in the repo; `.env` is never committed.
- Comments say *why*. Keep files focused; past ~300 lines, suggest a split.
- Commit messages say why. Commit and push only when asked.
