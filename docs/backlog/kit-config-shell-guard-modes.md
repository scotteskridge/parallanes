---
status: next
lane: any
size: M
---
# Decide which modes guard the kit's config from shell commands

The kit's ask rules are `Edit` rules: they stop Claude's file tools, but Claude Code doesn't say
they cover `rm`, redirections or PowerShell cmdlets. The hook blocks shell writes to the kit's
config in `bypassPermissions` only (decision 92). `acceptEdits` auto-approves common file commands,
`auto` and `dontAsk` can run commands unasked, and any mode runs a command an allow rule covers, so
`rm -rf .githooks` can get through there. Widening the block to those modes (review round 2 of
decision 92) blocked everyday commands: `cp file .`, `mv x .`, `cp notes.md .claude/`, `git restore
--staged .`.

Options from the review: block in every mode (the owner runs such commands with `!`); keep bypass
only and document the gap (today's state); or block only the commands each mode auto-approves.
Whichever is chosen, a write into a folder should count only the file it creates
(`<dest>/<name of source>`), and `git restore --staged` without `--worktree` writes no file (today it
is blocked in bypass mode). Related gaps: `.claude/settings.local.json` can hold permission rules but
isn't guarded; `git stash` and `git clean` aren't recognised as file commands. A live check of `rm`
and a redirection against an `Edit` ask rule in `acceptEdits` would show how big the gap really is.

**Done when:** the owner has picked an option, recorded in the decisions log; the hook, its tests
(blocked and allowed cases in every mode) and `protected-paths.md`'s Known misses match it.
