# 12 — Launch

**Status:** In progress
**Branch / PR:** `plan/12-launch` · PR link once open
**Builds on:** plans 00–09 and 07b (Done); decisions 73, 77, 81, 98, 104, 107, 108 (the answers), 109 (the name); backlog
`readme-builtins-comparison` and `plugin-name` (both folded in here); ARCHITECTURE §12

## Goal
A stranger can find `parallanes` on GitHub, understand in about two minutes what it adds over
Claude Code's own worktrees, check that claim against a real two-lane trial, and install v0.1.0
into their project by following the README alone.

## Out of scope
- The plugin and marketplace install (`ship-kit-as-plugin`, v0.2). Only the name is checked here.
- Plans 10 (Unity pack) and 11 (evals), `/onboard`, per-lane ports: v0.2.
- A demo GIF, FAQ, "why this design" page (ROADMAP §13, later).
- Renaming the kit's internals (see question 1).
- Publishing to PyPI: the kit installs by copying files (decision 78).

## Open questions
1. **How far does the rename to `parallanes` reach?** Decision 81 renames the repo and the CLI
   together. `kit.toml` alone appears ~1,100 times, and `.claude/kit/`, `kitlib`, the `KIT_*`
   variables and the `kit:protected-change` label are written into installed projects.
   *Recommendation:* rename what a reader types or sees: the GitHub repo, `pyproject` name, README
   and docs prose ("parallanes" for the product; "the kit" stays fine as a plain noun), and the
   command: the launcher `.claude/kit/kit` becomes `.claude/kit/parallanes`, so `{{kit_command}}`
   is `sh .claude/kit/parallanes` and messages start `parallanes:`. Keep the folder, `kit.toml`,
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
   repos' full history → push the trial repo to GitHub as `parallanes-trial` → rename this repo to
   `parallanes` → tag `v0.1.0` and create the release → make both repos public. Making a repo
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
  "Claude Code does / parallanes adds" table and the lanekeeper line (re-checked against the
  current docs through `claude-code-guide` before the README is written).
- `payload/placeholders.toml` `[kit_command]`, `installer/values.py` `KIT_COMMAND`: the one place
  the command is defined; tests already render it into every template.
- `CHANGELOG.md` `[Unreleased]` becomes `[0.1.0]`; `pyproject.toml` version `0.1.0.dev0` → `0.1.0`.
- `docs/live-checks.md`: the install-from-README check below follows its "say what loaded" rule.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `payload/kit-owned/.claude/kit/kit` → `parallanes` | Rename | launcher; message prefix `parallanes:` |
| `installer/values.py`, `placeholders.toml`, `cli.py` | Edit | command name, `prog`, message prefix |
| skills, templates, docs that show the command | Edit | `sh .claude/kit/parallanes …` |
| `README.md` | Rewrite | story → "does / adds" table → what the trial caught → 3-step quickstart → diagram → guardrail table → status → license |
| `pyproject.toml`, `CHANGELOG.md` | Edit | name `parallanes`, version `0.1.0`, release section |
| ROADMAP, ARCHITECTURE §12, plans index, decisions log | Edit | template repo dropped; answers logged |
| backlog `readme-builtins-comparison`, `plugin-name` → `done/`; new `template-repo` | Move / New | |
| `tests/` | Edit / New | below |

## Steps
1. Failing tests first: installed files call `sh .claude/kit/parallanes`, the old launcher is gone,
   no installed file mentions `.claude/kit/kit` or `claude-code-lanes-starter`.
2. Rename the launcher and the command everywhere it's shown; full suite and ruff green.
3. Check the name again: PyPI, npm, GitHub, a quick trademark search, and a scratch stub plugin
   named `parallanes` through `claude plugin validate --strict` (not committed; result in the PR).
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
| a fresh install has `.claude/kit/parallanes` and no `.claude/kit/kit` | the command is renamed |
| no installed file mentions `.claude/kit/kit` or the old repo name | nothing points at the old names |
| `sh .claude/kit/parallanes next` runs from a path with a space | the renamed launcher works on Windows |
| re-install over a v0.1.0.dev0 project reports the launcher change, keeps owner files | decision 100 still holds |
| README's quickstart commands appear verbatim in a test that runs them | the README can't drift from what works |

## Done when
- [x] Tests above pass locally and in CI (Windows + Ubuntu)
- [x] Reviewer report attached to the PR; every 🔴 fixed
- [x] Two-minute test and quickstart run recorded in the PR
- [ ] Both repos public, `v0.1.0` tagged with release notes, README links resolve
- [x] CHANGELOG, ROADMAP and decisions log updated where this plan changed them

## Notes after implementation
- **The name changed to `parallanes`** (decision 109). Step 3's check found `worklanes` already
  published as a Claude Code plugin (Deploy Forward, created 2026-10-02) and a "WORKLANE"
  trademark filing on software. The owner chose `parallanes`; this plan's text uses the new name.
  The stub plugin passed `claude plugin validate --strict` (Claude Code 2.1.293).
- **Upgrading an earlier install:** the installer never deletes, so `.claude/kit/kit` stays and
  the re-run says it's the old name; managed blocks under the old `claude-code-lanes-starter`
  markers are rewritten under the new ones; `kit_command` is no longer taken from the earlier
  manifest, since it would name a launcher this version doesn't ship.
- **The command's name in messages too:** what the CLI and hooks tell an agent to run names the
  launcher (`sh .claude/kit/parallanes lanes start <task>`), so it runs as given (the first
  version said a bare `parallanes ...`, which isn't on the PATH until the v0.2 plugin).
- **The README test caught the README:** the first quickstart said `--target ../my-project`,
  one folder too high; `tests/test_readme.py` now runs the quickstart's commands as written.
- **Two-minute test:** a fresh reader given only the README scored 4/5. Fixed from its notes:
  the second lane is shown, why not `--worktree` is said, jargon cut, and "inside the lane" and
  "PR or fast-forward" explained.
- **Built-ins re-checked** by `claude-code-guide` against the current docs: claims 1, 2, 4, 6 hold
  as written. The desktop app's base-branch sync and PR watching aren't in the docs it read, so
  the README doesn't claim them. No built-in path ownership or task cycle exists.
- `AGENTS.md`'s title became `# parallanes: rules for any coding agent` on the owner's OK.
- **Review round 1** (repo `reviewer` and a hands-on general reviewer, who re-ran an upgrade from
  `main` and the quickstart): 🔴 the quickstart never said to commit, so lanes came out without
  the kit, and the README test slipped in the commit itself. Now the README says it, the test
  takes every command from the README, and `lanes create` refuses a lane the tip's `kit.toml`
  doesn't declare (saying to commit, and push in PR mode). 🟠 a new folder's `git init` made
  `master` while lanes looked for `main`: the installer now says `git init -b main` and the error
  says how to fix it. 🟠 re-installing dropped the old launcher's LF rule; it's kept, and the note
  names the files still calling it. 🟠 the upgrade test now starts from a real old-style install.
  🟡 README claims matched to the trial write-up; 0.1.0 changelog names; markers match whole.
- **Review round 2** (fresh general reviewer on the round-1 fixes, reproducing each case; no 🔴):
  🟠 a lane declared at the tip but without the launcher committed still came out broken, so
  `lanes create` now also checks the tip has the launcher when the main checkout does. 🟡 a tip
  `kit.toml` that doesn't parse says so; the PR-mode hint mentions fetching; a tab or NBSP after
  the marker name is a marker again; a BOM before a block on line 1 is kept; a code fence without
  a language fails the README test. The five new tests failed before the fixes. The fixes are
  small and round 2 had no 🔴, so no third round (decision 79).
- **Follow-ups the owner asked for in this PR:** the old-launcher note is said when its list of
  callers changes (the manifest keeps the list), not on every run; and a test runs the README's
  PowerShell install line, which is in prose, not a code block (Windows only).
