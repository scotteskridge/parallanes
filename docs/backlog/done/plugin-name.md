---
status: next
lane: any
size: S
---
# Adopt the name `parallanes` everywhere

Decision 73 picked `worklanes`, replaced by `parallanes` (decision 109): `claude-` plugin names are reserved by `claude plugin validate`
([plugins-reference](https://code.claude.com/docs/en/plugins-reference.md#name)), and a published
plugin name can't change. Every component is namespaced under it (`parallanes:reviewer`), so it
shows up in daily use. Still open for the owner: whether the `kit` CLI command becomes `parallanes`
too (one name is easier to find; `kit` is short to type), and when to rename the GitHub repo
(GitHub redirects the old URL).

**Done when:** a stub plugin named `parallanes` passes `claude plugin validate --strict` with no
warning; the repo, README, `pyproject.toml` and docs use the name; the CLI question is decided
and logged; and the name is checked again on PyPI, npm and GitHub (and a quick trademark search)
just before launch.

**Done (plan 12):** `worklanes` turned out to be taken (a published Claude Code plugin, and a
"WORKLANE" trademark filing), so the kit is `parallanes` (decision 109). A stub plugin of that
name passed `claude plugin validate --strict` (Claude Code 2.1.293); PyPI, npm, GitHub and a web
search were clear on 2026-10-07. The command is `sh .claude/kit/parallanes` (decision 108); the
repo is renamed in the publish checklist.
