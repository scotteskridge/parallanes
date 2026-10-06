---
status: next
lane: any
size: S
---
# Pick a plugin name Claude Code accepts

`claude plugin validate` rejects plugin names starting with `claude-` as reserved, and warns on
`claude` as a whole word anywhere ([plugins-reference](https://code.claude.com/docs/en/plugins-reference.md#name)).
So `claude-code-lanes-starter` can't be the plugin name, and every component is namespaced under
the name (`<name>:reviewer`), so it shows up in daily use. Settle it before plan 08 and plan 12's
launch, since the repo name, README and decisions should agree.

**Done when:** the owner has picked a name that passes `claude plugin validate --strict` with no
warning, and it's recorded in the decisions log (renaming the repo is a separate call).
