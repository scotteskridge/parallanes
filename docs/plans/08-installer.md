# 08 — Installer

**Status:** In progress
**Branch / PR:** `plan/08-installer` · PR link once open
**Builds on:** plans 01–07 (Done); decisions 7, 19, 25, 29, 78; ARCHITECTURE §4, §10, §14 and the
§15 rows owned by plan 08

## Goal
Someone with git, Python 3.11+ and Claude Code runs one command (`install.ps1` or `install.sh`)
against a new folder or an existing repo. They get a working kit: kit-owned files copied in,
templates rendered, hooks and deny rules wired into `.claude/settings.json`, and a manifest. Nothing
they already had is overwritten, and `--dry-run` shows the whole file list first.

## Out of scope
- `/onboard`, which reads the repo and proposes stack facts, rules and lanes (v0.2). The installer
  asks only what it can't detect (decision 17).
- Packs and `--pack` (plan 10, v0.2), the plugin (`ship-kit-as-plugin`, v0.2), and a `kit update`
  command. A re-run of the installer is safe (step 5), but it is not an update tool.
- Uninstall and `doctor` (backlog `doctor-and-uninstall`); a non-interactive answers file (ROADMAP
  Later); the CI workflow template (plan 09).

## Open questions
1. **How people and agents run the kit (`{{kit_command}}`, ARCHITECTURE §15).** Options: root shims
   (`kit`, `kit.cmd`); `python .claude/kit/cli.py`; or `sh .claude/kit/kit`.
   **Recommend `sh .claude/kit/kit` everywhere, with no root shims.** The skills already use it
   (plan 07). It reads the gitignored `python-path`, so committed files never hold a machine's
   interpreter. `python …` can hit the Windows Store alias (decision 19). On Windows,
   `install.ps1` requires Git for Windows' `sh`, because the hook launcher needs it anyway (§15). A
   `kit.cmd` for people in plain PowerShell becomes a backlog item if the trial shows it's missed.
2. **What happens when a file already exists (§10 step 4).** **Recommend no prompt per file.** The
   rules by file type:
   - *Project-owned file that already exists:* the kit writes `<name>.kit-new` beside it and lists
     it in the next steps. The original is never touched.
   - *`.gitignore`, `.gitattributes`, `.worktreeinclude`:* the kit's lines go in a managed block
     (`# >>> claude-code-lanes-starter` … `# <<<`), added or replaced in place. A lone or doubled
     marker is an error, never silently repaired (the pattern from `survey-lanekeeper.md`).
   - *`settings.json`:* the kit's hook entries and permission rules are merged in, and the ones the
     kit wrote are recorded. Owner entries are never touched (decision 29, extended to hooks).
   - *Kit-owned file that differs from what the manifest recorded:* the kit writes `.kit-new` and
     reports it. Otherwise the file is replaced, so a re-run is safe.
   A prompt per file is slow and easy to answer wrongly; `--dry-run` already shows every case.
3. **What the installer asks.** **Recommend five values, each with a detected default:** project
   name (the folder name), a one-line description, the stack, the test command (detected from
   `pyproject.toml`, `package.json`, `go.mod` or `Cargo.toml`, else blank with a TODO), and the
   integration branch (from git, else `main`). It also asks one yes/no: enable the pre-commit hook
   (decision 25). It doesn't ask about lanes: `kit.toml` ships the commented example and
   `parallel-lanes.md` covers it. `--yes` takes every default, for tests and repeat installs.

## Reuse
- `payload/kit-owned/**` is copied as-is; `payload/templates/**` is rendered by
  `kitlib/render.py`, with names from `placeholders.toml`.
- `kitlib/settings.py` (`plan_sync`, `apply_sync`, `write_json`) writes the deny and ask rules and
  keeps the owner's JSON style. The hook merge follows the same approach.
- `.claude/kit/hook` (fails closed) and `.claude/kit/kit` read `python-path`.
  `tests/test_kit_launcher.py` shows how to test a launcher.
- `kitlib/config.py` loads the rendered `kit.toml` once, as a smoke test that it parses.
- `tests/helpers.py` and `tests/lane_helpers.py` provide temp repos and paths with spaces.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `install.ps1`, `install.sh` | New | Thin bootstrappers. Find a real Python ≥ 3.11 (skipping the Store alias); check git, `sh` and Claude Code, and gh (optional); then run `kit_setup.py` with the arguments passed through |
| `kit_setup.py`, `installer/*.py` | New | The installer, split into detect, plan (the file list and the action for each file), write, and settings. It imports kitlib from `payload/`. Stdlib only |
| `payload/kit-owned/.claude/kit/hook` | Edit | Fail closed only for `protected` and `reviewer-bash`. Other hooks pass the exit code through, so a missing Python never blocks the fail-open ones (decisions 9, 40, 41) |
| `payload/placeholders.toml` | Edit | `kit_command` example set to `sh .claude/kit/kit` |
| `.claude/kit/manifest.json` (written) | New | Kit version, SHA-256 of each kit-owned file, the hook entries the kit wrote. `generated-rules.json` stays as it is (decision 29) |
| `docs/ARCHITECTURE.md`, `ROADMAP.md`, `CHANGELOG.md`, decisions log | Edit | Close the §15 rows for plan 08; record the answers |

## Steps
1. Failing tests first: the rendered `kit.toml` with a test command containing `"` and `\` (TOML
   escaping, §15); interpreter detection skipping a Store-alias stub; the dry run lists every file
   with its action and writes nothing.
2. Detection and questions (Q3), with `--yes` and `--target DIR`, including paths with spaces.
3. The file plan and its writes: copy, render (LF endings), `.kit-new` and managed blocks (Q2).
   Write `python-path` (gitignored) and the manifest.
4. Settings: run `settings sync` for the deny and ask rules, then merge the hook wiring as
   `sh "$CLAUDE_PROJECT_DIR/.claude/kit/hook" <name>`. That is the form the reviewer guard already
   uses live; whether placeholders expand in the `args` form isn't documented. The wiring:
   - `protected`: PreToolUse, matcher `Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit`
   - `ownership`: PreToolUse, matcher `Edit|Write|MultiEdit|NotebookEdit`
   - `rules-check`: PostToolUse
   - `lane-router`: SessionStart

   Change the `hook` launcher's fail mode to match each hook.
5. A re-run over an unchanged install changes nothing. A re-run after a kit-owned file was edited
   writes `.kit-new` and says so.
6. Pre-commit: on a yes, `git config core.hooksPath .githooks`; skipped without git.
7. Bootstrappers and next steps: open Claude Code in the project once and accept the trust dialog
   (§15, plan 06); review any `.kit-new` files; edit `kit.toml` to add lanes.
8. Live check: install into a scratch repo, then a headless session there shows that the
   protected, ownership and lane-router hooks fire from the installed `settings.json` and that a
   deny rule bites (Windows; macOS/Linux noted as not run if they weren't).

## Tests
| Test | Proves |
| --- | --- |
| Install into an empty folder and into an existing repo, both with spaces in the path | Every planned file lands, LF endings, the manifest hashes match |
| Existing `CLAUDE.md`, `.gitignore`, `settings.json` with owner hooks and rules | `.kit-new` written beside the first; managed block added to the second; owner entries kept in the third |
| Broken managed block (lone marker) | The installer stops with a clear message and writes nothing |
| `--dry-run` | Prints the plan; the folder's file tree and hashes are unchanged |
| Test command with quotes and backslashes | The rendered `kit.toml` loads with `config.py` |
| Interpreter detection with a Store-alias stub first on PATH | The real interpreter is chosen and written to `python-path` |
| `hook` launcher with no Python, for each hook name | `protected` and `reviewer-bash` exit 2; the others don't block |
| Re-run unchanged / after an edit | No changes / `.kit-new` written for the edited kit-owned file |
| After install: `sh .claude/kit/kit check all` and `kit check settings` | The installed kit runs, and settings agree with `kit.toml` |

## Done when
- [ ] Tests above pass locally and in CI (Windows + Ubuntu)
- [ ] Reviewer report attached to the PR; every 🔴 fixed
- [ ] Live check in `tests/live/` (step 8), run with `--live`
- [ ] CHANGELOG, ROADMAP, ARCHITECTURE §15 and the decisions log updated

## Notes after implementation
- **Layout:** `kit_setup.py` plus an `installer/` package (`values`, `plan`, `blocks`,
  `settings_hooks`, `main`, `report`), importing kitlib straight from the payload. Everything is planned
  before anything is written, so `--dry-run` and the real run print the same list, and a broken
  managed block stops the install with nothing written.
- **Project-owned files on a re-run:** the manifest also lists the templates the kit rendered, so a
  re-run never touches them again (decision 7), even after the owner edits them. Only a file the
  owner had *before* the kit gets a `.kit-new`. The manifest keeps the answers too, so a re-run
  renders the same files (the install date included).
- **Python:** `python-path` holds the interpreter that ran the installer (`sys.executable`). The
  bootstrappers pick it by running each candidate, and the `py` launcher reports the real
  interpreter it chose. Nothing is skipped by path: review round 1 found real pythons under
  `WindowsApps` (python.org's install manager, Store Python), and the alias fails the probe anyway.
- **New folder:** no `git init`; the next steps say to run it and turn on the pre-commit check. A
  subfolder of a repo gets no pre-commit and no `git init` advice; the owner's own hooks in
  `.git/hooks` keep the pre-commit check off (`core.hooksPath` would switch them off).
- **Review round 1** (repo `reviewer` plus a general-purpose reviewer; both found the 🔴): a file the
  owner had at a kit-owned path got the *owner's* hash recorded, so the second run replaced it.
  Fixed with 36 tests written first (all failing on the round-1 code), split into
  `test_installer_units.py`, `test_installer_safety.py` and the ps1 tests. Also: `.kit-new`
  offered once, a broken manifest stops, hook groups found by command, the launcher fails open on a
  missing `cli.py`, `.gitignore` covers bytecode and `*.kit-new`, the dry run lists every file, BOM
  and mixed endings kept, the kit repo itself refused as a target, next steps read the files.
  `.gitattributes` with the owner's rules gets only the kit's `eol=lf` lines (decision 100, flagged
  for the owner).
- **`.claude/kit/VERSION`** is written as a kit-owned file, as ARCHITECTURE §4 lists it.
- **Live check** (`tests/live/test_installed_kit.py`, Windows, Claude Code with haiku): all four
  hooks fired from the installed `settings.json`, the protected hook blocked a `cp` into `vendor/`
  (exit 2, its own message), and the generated deny rule refused a Write. Not run: macOS/Linux.
- Dev-only: ruff's `src` gained `"."` so `installer` sorts as first-party.
