---
status: next
lane: any
size: S
---
# `[[shared]]` tables add to the default shared paths

Plan 13 (decision 116) shipped with "writing any `[[shared]]` table replaces the defaults", as
`shared_paths` always did. Review round 1 found the catch: the trial's F8 fix is to add one `ask`
table for `.gitignore` and `package.json`, and a project that writes only that table loses
`docs/changelog.d/**`, `docs/plans/**` and `docs/backlog/**` as shared paths. Every lane's
`/wrap-up` commit that touches them is then refused ("no lane owns it"), and the stop's fix offers
the fragment to one lane's `owns`. The `kit.toml` template warns about it for now.

**Decided (owner, 2026-10-18, on Claude's recommendation; decision 116):** tables add to the
defaults, with a switch to turn the defaults off for the rare project that wants to drop or loosen
one (e.g. `shared_defaults = false` in `[project]`; the exact key is this item's to settle). A
written `shared_paths` list keeps its v0.1 meaning and still replaces the defaults, so existing
projects don't change. A table can already make a default stricter (the stricter mode wins).

**Done when:** a `kit.toml` with only the repo-wide `ask` table keeps every default shared path;
the switch drops them; the loader, template, lane guide, ARCHITECTURE §6 and decision 116 say the
same; tests cover add, the switch, and `shared_paths` still replacing.
