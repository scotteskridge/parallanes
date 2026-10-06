---
status: later
lane: any
size: L
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

Decided for v0.2 (decision 78): v0.1 installs by copying files, with kit-owned files kept in a
layout that can become the plugin's. Hook launch paths, the stdlib-only rule and decision 7
(kit-owned vs project-owned) all apply.

Constraints found since (`docs/survey-claude-code.md`, plan 08): plugin agents ignore `hooks`
frontmatter, so the reviewer's guard must move into the plugin's hooks; `bin/` is on the PATH of
Claude's Bash tool only, so pre-commit, CI and people's terminals need another route to the checks;
`userConfig` can replace `.claude/kit/python-path`; packs can be dependent plugins.

**Done when:** the kit installs with `/plugin install` plus one setup command, and updates without overwriting
project-owned files.
