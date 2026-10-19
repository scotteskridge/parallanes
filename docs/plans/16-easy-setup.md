# 16 — Easier setup: profiles and suggested lanes

**Status:** Approved
**Branch / PR:** `plan/16-easy-setup` · PR link once open
**Builds on:** decisions 121–123 (this plan's answers); plan 08 (the installer) and decisions 100–102 (no overwrites, five questions, hook
switches); decision 99 (`sh .claude/kit/parallanes`); decision 120 (the per-call hooks' cost);
ARCHITECTURE §10. Revisits decision 101's "no lane questions".

## Goal
Someone who wants one agent installs the kit and is done: they get the guardrails and the plan →
implement → wrap-up loop without the lane machinery. Someone who wants lanes answers the
installer's questions and ends up with lanes written, the kit committed and the lane folders
created, ready to open, with no hand-edited TOML.

Today the README's quickstart is 4 steps and about 6 commands, plus hand-writing `[[lanes]]` in an
827-word `kit.toml`, before the first lane session. After this plan it's clone, install and answer,
then open the lane folders.

## Out of scope
- Installing as a Claude Code plugin (backlog `ship-kit-as-plugin`, v0.2 step 5) and the agentic
  `/onboard`, which can refine lanes later. This plan is the deterministic installer path both build on.
- `lanes open` (starting a Claude Code session per lane): terminals differ on every OS. This plan
  prints each lane's exact command instead. To add on approval: backlog `lanes-open`.
- Leaving `/design` and `/code-health` out of the solo profile (their descriptions cost a few
  hundred tokens a session). To add on approval: backlog `solo-profile-extras`.

## Open questions
1. **Which profile is the default?** *Recommendation: solo.* The installer asks one more yes/no,
   "Run several agents at once, each in its own lane? [y/N]", and `--profile solo|lanes` answers it
   for scripts. Solo is useful on its own and doesn't pay for the ownership hook on every edit
   (~270 ms on Windows after plan 15). Lanes are one re-run away (`--profile lanes`). *What would
   change it:* if most people who find the kit come for lanes (its name says so), default to lanes.
2. **Suggest lanes now, or wait for `/onboard`?** *Recommendation: now, deterministically.* A
   folder-based guess (`src/<x>/`, or top-level folders such as `server/` and `public/`, with
   `tests/<x>/` folded in) is shown, and written only on a yes. That keeps decision 101's point:
   the owner decides, with a draft in front of them instead of a blank table. `/onboard` can later
   propose better splits from reading the code. *What would change it:* if the guess is wrong on the
   trial project and two others, drop it and wait for `/onboard`.
3. **May the installer commit for you?** *Recommendation: offer it, interactively only.* It asks
   "Commit the kit's files now? [Y/n]" only when the folder is a repository root, has a commit and
   had no changes before the install, so the commit holds only the kit's files. It runs the
   pre-commit hook, never pushes, and never commits under `--yes` or `--dry-run`. With lanes and no
   `origin` remote, it then offers to run `lanes create`. With an `origin`, it says to push first.
   *What would change it:* if you'd rather the installer never touch git history, it prints the two
   commands instead.

## Reuse
- `installer/values.py`: `QUESTIONS`, `confirm()` and detection. The profile question goes beside
  the pre-commit question.
- `installer/settings_hooks.py`: `expected(off=...)` already leaves hooks out; solo adds
  `lane-router` and `ownership` to `off`, and a re-run with `--profile lanes` adds them back (decision 102).
- `installer/main.py`: the manifest's saved answers (the profile is saved with them); `report.next_steps`.
- `kitlib/lane_setup.create` and its "commit the kit's files" check; `kitlib/config.py`'s lane-name rules.
- `tests/test_readme.py`: runs the README's quickstart as written, so the new quickstart is tested.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `payload/kit-owned/.claude/kit/kitlib/lane_suggest.py` | New | The folder-based guess: tracked folders only (`git ls-files`); skips dot-folders, `docs`, `tests`, `build`, `dist`, `vendor`; 2–5 lanes or none, with the reason |
| `payload/kit-owned/.claude/kit/cli.py` | Edit | `lanes suggest`: prints the `[[lanes]]` tables, or why there's no guess (read-only) |
| `installer/values.py`, `installer/main.py` | Edit | Profile question and `--profile`; lane suggestion and append; commit and `lanes create` offers |
| `installer/report.py` | Edit | Next steps follow what was done: each lane's open command, or what's left |
| `payload/templates/.claude/kit.toml.tmpl` | Edit | Values plus one-line comments (~200 words); the full reference moves out |
| `payload/templates/docs/ai/kit-toml.md.tmpl` | New | Every `kit.toml` key with its example, from today's comments |
| `README.md`, `docs/ai/parallel-lanes.md.tmpl`, `docs/ARCHITECTURE.md` §10 | Edit | Shorter quickstart; `lanes suggest`; the installer flow |

## Steps
1. Failing tests for `lane_suggest`: `src/<a>,<b>`; `server/` + `public/`; `tests/<x>` folded in;
   one folder or more than five gives none, with a reason; names made valid; untracked folders ignored.
2. Implement `lane_suggest` and `lanes suggest`.
3. Failing tests, then the profile: question, `--profile`, saved in the manifest; solo leaves out two
   hooks; a re-run with `--profile lanes` adds them; installing twice changes nothing.
4. Failing tests, then the lane offer (append to `kit.toml` on a yes; skipped when it already has
   `[[lanes]]`; shown by `--dry-run`).
5. Failing tests, then the commit and `lanes create` offers, under each condition in question 3.
6. Lean `kit.toml` template plus `docs/ai/kit-toml.md`; template tests updated to the new home.
7. README quickstart, next steps and docs; `test_readme.py` passes on the new quickstart.

## Tests
| Test | Proves |
| --- | --- |
| `test_lane_suggest.py` (new) | The guess for each layout, and no guess where it would be wrong |
| `test_installer.py`: profile cases | Solo has no lane hooks; switching to lanes adds them; re-runs are stable |
| `test_installer_safety.py`: commit cases | No commit on a dirty tree, a non-root, no commit yet, `--yes` or `--dry-run`; never a push |
| `test_readme.py` | The new quickstart works as written, on Windows and Ubuntu |

## Done when
- [ ] Tests above pass locally and in CI (Windows + Ubuntu)
- [ ] Reviewer report attached to the PR; every 🔴 fixed
- [ ] A fresh install on the trial project's first commit, answered "lanes", ends with two lane
      folders and no hand edits; the transcript goes in the PR
- [ ] CHANGELOG, ROADMAP (§1, §6) and decisions log updated

## Notes after implementation
- **Going back to solo works too.** The plan left it out because the installer never deletes, but
  hooks aren't files: `--profile solo` removes the two hooks the kit wrote, as a `[hooks]` switch
  already did (decision 102). Decision 121 is refined to say so.
- **`lanes create` points out missing lane hooks.** With solo the default, lanes written by hand
  after a solo install would run without the ownership check. `lanes create` now says to re-run the
  installer with `--profile lanes`, and lanes in `kit.toml` make the next re-run choose lanes.
- **An install from before profiles keeps every hook.** Its manifest has answers but no profile, so
  it counts as lanes; otherwise upgrading would have quietly removed two hooks.
- **Tests that exercise the lane hooks install with `--profile lanes`.** These are the four live
  checks, `tools/hook_timing.py`, three installer tests and the README test (whose `--yes` stands
  for the README's answers). The two tests that type their answers also answer the new question.
  What each checks is unchanged.
- **The next steps list each lane's folder, not a command.** `cd x && claude` doesn't parse in
  Windows PowerShell 5.1.
- **The commit marks `.githooks/pre-commit` executable** (`git add --chmod=+x`), which the
  Windows next step used to ask the owner to do.
- **Follow-ups filed:** `lanes-open`, `solo-profile-extras`, and `installer-main-split`.
  `installer/main.py` grew to 308 lines, and the installer's `toml_string` duplicates
  `lane_owners.toml_string`, which this plan made public for `lanes suggest`.
