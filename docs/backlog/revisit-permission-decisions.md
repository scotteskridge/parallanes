---
status: now
lane: any
size: S
---
# Revisit the permission decisions the docs now contradict

From `docs/survey-claude-code.md`, "Decisions to revisit":

- Decision 30's reason is wrong: ask rules prompt in every mode, including `bypassPermissions`
  ([permission-modes](https://code.claude.com/docs/en/permission-modes.md)). The hook block for kit
  config in bypass mode may be unnecessary. This also answers ARCHITECTURE §15's acceptEdits row.
- Decision 31: a deny rule starting with `!` is a gitignore negation, so `.env.*` plus
  `!.env.example` is now possible ([permissions](https://code.claude.com/docs/en/permissions.md)).
- Only `Edit(path)` and `Read(path)` path rules are consulted; `kit settings sync` should be tested
  to emit nothing else.
- `Read`/`Edit` deny rules now cover Bash file commands Claude Code recognizes; the backstop's
  overlap should be narrowed or labelled a drift guard.
- `docs/ai/protected-paths.md` should name the Windows sandbox options (WSL2, a container, a VM).

**Done when:** one live session confirms the ask-rule behaviour; decisions 30 and 31 are updated or
superseded by new entries; the settings-sync test exists; `protected-paths.md.tmpl` and §15 match.
