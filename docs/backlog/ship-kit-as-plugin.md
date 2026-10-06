---
status: next
lane: any
size: L
blocked_by: plan 08 scope decision
---
# Ship the kit-owned parts as a Claude Code plugin

A plugin can ship skills, agents, hooks and a `bin/` folder (on the Bash tool's PATH, so the
`kit` CLI could live there). It updates through a marketplace, and a project-scope install also
loads in the project's worktrees ([plugins-reference](https://code.claude.com/docs/en/plugins-reference.md),
[worktrees](https://code.claude.com/docs/en/worktrees.md)). That would make the roadmap's Later
"update command" and "plugin packaging" nearly free, and is how real users expect to install tools.

What a plugin can't ship, so plan 08 still needs a setup step for it: permission deny rules
(plugin `settings` only applies `agent` and `subagentStatusLine`), `CLAUDE.md`/`AGENTS.md`
(a `CLAUDE.md` at the plugin root isn't loaded), and project-owned files (`kit.toml`, templates,
`.claude/rules/`). That step could be `/onboard` or `kit init`.

Open for the owner (plan 08): plugin plus a small project setup, or the installer as planned?
Hook launch paths, the stdlib-only rule and decision 7 (kit-owned vs project-owned) all apply.

**Done when:** plan 08's scope records the choice in the decisions log, and if it's the plugin,
the kit installs with `/plugin install` plus one setup command, and updates without overwriting
project-owned files.
