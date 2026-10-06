---
status: now
lane: any
size: S
---
# Check that lane settings are read from the lane on macOS and Linux

Decision 35 has `lanes create` write `claudeMdExcludes` into each lane's own
`.claude/settings.local.json`, so a lane doesn't load the main checkout's instructions. The settings
docs say that in a worktree Claude Code "uses the file at the main checkout's root", and keeps it
with the worktree only "on Windows" and a few other cases
([settings](https://code.claude.com/docs/en/settings.md)). It was verified live on Windows only. On
macOS and Linux every lane may silently read the main checkout's file, so the excludes (and any
other lane-local setting) wouldn't apply. See `docs/survey-claude-code.md`.

**Done when:** a live run on macOS or Linux shows which file a lane session reads; if it's the main
checkout's, the owner picks a fix (another place for the excludes, the sibling-folder layout
decision 35 already names as the fallback, or per-lane entries in the main file), and it's recorded
in the decisions log and ARCHITECTURE §15.
