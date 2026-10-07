# 09 — CI template

**Status:** Done
**Branch / PR:** `plan/09-ci-template` · https://github.com/scotteskridge/claude-code-lanes-starter/pull/37
**Builds on:** plans 02, 03, 04 and 08 (Done); decisions 25, 32, 34, 95, 96; ARCHITECTURE §4, §7
and the §15 row owned by plan 09

## Goal
An installed project gets `.github/workflows/kit.yml`. It runs the project's tests and
`kit check all` on every push and PR, so the rules, protected paths, settings drift and lane
boundaries are enforced where an agent can't switch them off. The docs also say how to make that
check required (branch protection) and how a human lets an intended protected-path change through.

## Out of scope
- Annotations and a step summary on the PR page (`ci-check-annotations`, later).
- `CODEOWNERS` from lanes (`codeowners-from-lanes`: lanes have no owners yet).
- Judging a merge commit's protected paths on its resolution only (`protected-check-merge-commits`).
- Other CI hosts (GitLab, Azure): GitHub only for v0.1.
- Changing the repo's settings for the owner: the kit prints the steps and never calls the GitHub
  API itself.

## Open questions
1. **How does a PR declare an intended protected change?** Today CI has no override (decision 34),
   so a PR that edits a protected path on purpose can never go green.
   *Recommendation:* a PR label, `kit:protected-change`. The workflow re-runs on `labeled` and
   `unlabeled`, and sets `KIT_ALLOW_PROTECTED=1` only for the protected check while the label is
   on. Adding labels needs write access, and `gh pr edit --add-label` and `gh label` join the
   default `[protected].commands`, so an agent can't approve its own change. A commit trailer was
   the other option, but the agent writes the commits. `KIT_ALLOW_CROSS_LANE` gets no label: a
   cross-lane change still goes through a non-lane branch (ARCHITECTURE §6).
2. **`CODEOWNERS`: generate it, or document it?** The §15 row asks for entries from
   `[protected].paths`, but the kit doesn't know the owner's GitHub handle, and the paths change
   after install.
   *Recommendation:* document it for v0.1. `docs/ai/protected-paths.md` gets a "Server side"
   section with a `CODEOWNERS` example for the protected paths plus `.claude/` and `.github/`, and
   the branch-protection steps (required check, required review, no force pushes). Generating it
   joins `codeowners-from-lanes`, which needs the same owner field.
3. **What does the tests job know about the project's stack?** The kit can't know how to install
   a Node or Rust project's dependencies.
   *Recommendation:* two jobs. `kit-checks` is fully known: Python 3.13, full history, then
   `kit check all --diff <base>`. `tests` runs the installed `test_command` on `ubuntu-latest`,
   after a clearly marked "set up your stack here" step that has `actions/setup-python` filled in
   for a Python stack and a comment otherwise. If `test_command` is empty, the job fails and says
   to set it, rather than passing with nothing tested.

## Reuse
- `.github/workflows/tests.yml`: the `concurrency` block (decision 95) and the pinned action versions.
- `cli.py run_check` with `--diff BASE`; `gitfiles.touched_since` (`BASE...HEAD`); the lane from
  `GITHUB_HEAD_REF` (`lane_boundary.py`).
- `protected.ALLOW_VARIABLE` (`KIT_ALLOW_PROTECTED`), `commands.disables_checks` for the defaults.
- Installer templates (`payload/templates/*.tmpl`, `placeholders.toml`): the workflow is a
  project-owned template, so the existing no-overwrite path covers a project that already has one.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `payload/templates/.github/workflows/kit.yml.tmpl` | New | the two jobs; base is `origin/${{ github.base_ref }}` on a PR and `github.event.before` on a push |
| `payload/templates/.claude/kit.toml.tmpl` | Edit | `gh pr edit --add-label` and `gh label` in default `[protected].commands` |
| `payload/templates/docs/ai/protected-paths.md.tmpl` | Edit | "Server side": the label, `CODEOWNERS` example, branch protection |
| `installer/` (report) | Edit | next steps: push, then make `kit-checks` and `tests` required |
| `tests/test_ci_template.py` | New | below |
| ARCHITECTURE §4, §6, §15; decisions log; CHANGELOG | Edit | |

## Steps
1. Failing tests first: the rendered workflow parses, and its runs, base refs and label gate are
   what the table below says.
2. Write the template; render it in a scratch repo and run its `kit check` step locally with the
   CI environment variables set, on a clean diff, a protected change and a cross-lane change.
3. Add the default protected commands and the docs section; the installer's next steps.
4. Live check: push a scratch project to a private GitHub repo; show a green run, a red run on a
   protected change, and green again after adding the label.
5. Reviews, docs, PR.

## Tests
| Test | Proves |
| --- | --- |
| rendered `kit.yml` is valid YAML with both jobs | the template renders for the example values |
| `kit-checks` checks out with `fetch-depth: 0` and passes the right base for push and PR | `--diff` has history to diff against |
| `KIT_ALLOW_PROTECTED` is set only on the protected step, only from the label | the override can't leak to the other checks |
| `pull_request` types include `labeled` and `unlabeled` | adding the label re-runs CI |
| empty `test_command` makes the tests job fail with a message | nothing passes untested |
| the hook blocks `gh pr edit --add-label …` and `gh label create …` | an agent can't approve its own protected change |
| installing over an existing `kit.yml` keeps it and reports it | decision 7: never overwrite |

## Done when
- [x] Tests above pass locally and in CI (Windows + Ubuntu)
- [x] Reviewer report attached to the PR; every 🔴 fixed
- [x] Live check: the three runs on a real GitHub repo, linked from the PR
- [x] CHANGELOG, ROADMAP and decisions log updated where this plan changed them

## Notes after implementation
- **A push checks the whole project**, not `--diff github.event.before`: judging the merged change
  again would turn the integration branch red after every labelled protected change (decision 104).
- **`kit test`** is new: CI runs `test_command` from `kit.toml` instead of holding a copy of it.
- **The blocked `gh` commands** are `pr edit --add-label`, `issue edit --add-label`, `pr create
  --label`/`-l`, `label edit`, `alias set` and `pr merge --admin`, not `gh label` (which would block
  `gh label list`). The matcher drops gh's `-R`/`--repo` wherever it sits, reads `gh pr new` as
  `gh pr create`, and `--opt=value` as `--opt`, for every program.
- **The renderer:** `\{{` now escapes braces whatever follows, so GitHub's `${{ }}` survives.
- **PyYAML** is a dev-only dependency, so the tests parse the workflow instead of matching its text.
- **Review round 1** (repo reviewer and a hands-on general reviewer; decision 105): CI could be
  switched off by editing `kit.yml` in the PR (🔴, now kit config with an ask rule, and the limit is
  stated); the label waived secrets and later pushes; the branch-protection recipe locked out a solo
  owner; several `gh` forms got past the hook; CI's message pointed at a terminal-only override.
- **Review round 2** (fresh general reviewer on the fix commit): 🔴 the label was honoured again
  after an agent's `gh pr close`/`reopen` or another label's removal; now only the run its own
  `labeled` event starts counts. Also: a committed secret couldn't be deleted through a PR, a
  secret under a protected path was told to get the label, `-R` as another option's value hid a
  label flag, `gh alias import`, `-lvalue`.
- **Review round 3** (fresh reviewer on the round-2 fixes; no 🔴): gh reads options before its
  subcommand words (`gh pr --add-label x edit`), and short options cluster (`-dlvalue`); a separate
  value holding a space (`-m "-n removed"`) was wrongly read as an option; "deleted" now comes from
  git, not the disk; `gh extension` and `gh run rerun` are listed as misses.
- **Review round 4** (on the round-3 matcher; no 🔴): `gh pr -R o/r new -l` slipped past (the
  alias after an option's value); gh's clustering now stops at an option that takes a value, so
  `-tlogin` is a title. Two rare false positives are accepted (`gh label list --search edit`).
- **Live check** on a private scratch repo, `scotteskridge/worklanes-ci-check`: see the PR.
