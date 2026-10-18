---
status: idea
lane: any
size: S
---
# Should a `[[shared]]` table add to the default shared paths?

Plan 13 (decision 116) settled that writing any `[[shared]]` table replaces the defaults, as
`shared_paths` always did. Review round 1 found the catch: the trial's F8 fix is to add one `ask`
table for `.gitignore` and `package.json`, and a project that writes only that table loses
`docs/changelog.d/**`, `docs/plans/**` and `docs/backlog/**` as shared paths. Every lane's
`/wrap-up` commit is then refused ("no lane owns it"), and the stop's fix offers the fragment to
one lane's `owns`. The `kit.toml` template now says to uncomment the default tables with it.

Open for the owner: keep "replaces" (explicit, and what v0.1 did), or make `[[shared]]` tables add
to the defaults, with a way to drop one (e.g. `defaults = false` or a zone with `mode = "none"`).

**Done when:** the owner has chosen, and the loader, template and guide say the same.
