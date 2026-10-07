# 12 — Launch

**Status:** Approved
**Branch / PR:** `plan/12-launch` · PR link once open
**Builds on:** plans 00–09 and 07b (Done); decisions 73, 77, 81, 98, 104, 107, 108 (the answers); backlog
`readme-builtins-comparison` and `plugin-name` (both folded in here); ARCHITECTURE §12

## Goal
A stranger can find `worklanes` on GitHub, understand in about two minutes what it adds over
Claude Code's own worktrees, check that claim against a real two-lane trial, and install v0.1.0
into their project by following the README alone.

## Out of scope
- The plugin and marketplace install (`ship-kit-as-plugin`, v0.2). Only the name is checked here.
- Plans 10 (Unity pack) and 11 (evals), `/onboard`, per-lane ports: v0.2.
- A demo GIF, FAQ, "why this design" page (ROADMAP §13, later).
- Renaming the kit's internals (see question 1).
- Publishing to PyPI: the kit installs by copying files (decision 78).

## Open questions
1. **How far does the rename to `worklanes` reach?** Decision 81 renames the repo and the CLI
   together. `kit.toml` alone appears ~1,100 times, and `.claude/kit/`, `kitlib`, the `KIT_*`
   variables and the `kit:protected-change` label are written into installed projects.
   *Recommendation:* rename what a reader types or sees: the GitHub repo, `pyproject` name, README
   and docs prose ("worklanes" for the product; "the kit" stays fine as a plain noun), and the
   command: the launcher `.claude/kit/kit` becomes `.claude/kit/worklanes`, so `{{kit_command}}`
   is `sh .claude/kit/worklanes` and messages start `worklanes:`. Keep the folder, `kit.toml`,
   `kitlib`, `KIT_*` and the label. *Why:* the command is what people type and what the v0.2
   plugin will put on the PATH, so it should be the same name from day one; the internal names
   are invisible in daily use, and renaming them is a large diff with real breakage risk for no
   reader-visible gain. The decisions log keeps its old wording (it's history).
   *What would change it:* if you'd rather have one name everywhere before anyone installs it,
   this is the cheapest moment; it roughly triples the plan's size.
2. **Who presses the publish buttons, and when?** Renaming the repo, making it and the trial repo
   public, and tagging the release can't be undone quietly (a public repo can be cloned at once).
   *Recommendation:* the code and README land in a normal PR first. After it merges, Claude runs
   a short publish checklist one step at a time, each with your "yes" in chat: secret scan of both
   repos' full history → push the trial repo to GitHub as `worklanes-trial` → rename this repo to
   `worklanes` → tag `v0.1.0` and create the release → make both repos public. Making a repo
   public stays your click if you prefer.
3. **Drop the "GitHub template repository" from v0.1?** ROADMAP and ARCHITECTURE §12 list it, but
   marking this repo a template would hand people the kit's *development* repo, not a set-up
   project; a pre-installed blank project would carry a `python-path` from my machine.
   *Recommendation:* drop it from v0.1 and file backlog `template-repo` (later). The installer
   already covers a brand-new folder, and the published trial repo shows what an installed
   project looks like. ROADMAP §12 and ARCHITECTURE §12 change to say so.

## Reuse
- `docs/trial/two-lane-trial.md`: the "In short" and the task table are the README's evidence.
- `docs/survey-claude-code.md`, decision 98, backlog `readme-builtins-comparison`: the
  "Claude Code does / worklanes adds" table and the lanekeeper line (re-checked against the
  current docs through `claude-code-guide` before the README is written).
- `payload/placeholders.toml` `[kit_command]`, `installer/values.py` `KIT_COMMAND`: the one place
  the command is defined; tests already render it into every template.
- `CHANGELOG.md` `[Unreleased]` becomes `[0.1.0]`; `pyproject.toml` version `0.1.0.dev0` → `0.1.0`.
- `docs/live-checks.md`: the install-from-README check below follows its "say what loaded" rule.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `payload/kit-owned/.claude/kit/kit` → `worklanes` | Rename | launcher; message prefix `worklanes:` |
| `installer/values.py`, `placeholders.toml`, `cli.py` | Edit | command name, `prog`, message prefix |
| skills, templates, docs that show the command | Edit | `sh .claude/kit/worklanes …` |
| `README.md` | Rewrite | story → "does / adds" table → what the trial caught → 3-step quickstart → diagram → guardrail table → status → license |
| `pyproject.toml`, `CHANGELOG.md` | Edit | name `worklanes`, version `0.1.0`, release section |
| ROADMAP, ARCHITECTURE §12, plans index, decisions log | Edit | template repo dropped; answers logged |
| backlog `readme-builtins-comparison`, `plugin-name` → `done/`; new `template-repo` | Move / New | |
| `tests/` | Edit / New | below |

## Steps
1. Failing tests first: installed files call `sh .claude/kit/worklanes`, the old launcher is gone,
   no installed file mentions `.claude/kit/kit` or `claude-code-lanes-starter`.
2. Rename the launcher and the command everywhere it's shown; full suite and ruff green.
3. Check the name again: PyPI, npm, GitHub, a quick trademark search, and a scratch stub plugin
   named `worklanes` through `claude plugin validate --strict` (not committed; result in the PR).
4. Write the README; re-check every "Claude Code does" row against the current docs with links.
5. Two-minute test: a fresh-context subagent given only the README says what it is, why not the
   built-ins, and how to install; then follows the quickstart verbatim in a scratch folder with a
   space in its path, and `lanes create` works.
6. Version, changelog, docs; reviews (repo `reviewer` + a general reviewer told to run the
   quickstart); PR; merge on your approval.
7. The publish checklist from question 2, one confirmed step at a time; then a final install from
   the public URL on a clean folder.

## Tests
| Test | Proves |
| --- | --- |
| a fresh install has `.claude/kit/worklanes` and no `.claude/kit/kit` | the command is renamed |
| no installed file mentions `.claude/kit/kit` or the old repo name | nothing points at the old names |
| `sh .claude/kit/worklanes next` runs from a path with a space | the renamed launcher works on Windows |
| re-install over a v0.1.0.dev0 project reports the launcher change, keeps owner files | decision 100 still holds |
| README's quickstart commands appear verbatim in a test that runs them | the README can't drift from what works |

## Done when
- [ ] Tests above pass locally and in CI (Windows + Ubuntu)
- [ ] Reviewer report attached to the PR; every 🔴 fixed
- [ ] Two-minute test and quickstart run recorded in the PR
- [ ] Both repos public, `v0.1.0` tagged with release notes, README links resolve
- [ ] CHANGELOG, ROADMAP and decisions log updated where this plan changed them

## Notes after implementation
<!-- Filled in at wrap-up: what changed from the plan and why. -->
