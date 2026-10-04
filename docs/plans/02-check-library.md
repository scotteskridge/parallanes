# 02 — Check library, `kit` CLI and rules-check

**Status:** Done
**Branch / PR:** `plan/02-check-library`
**Builds on:** ARCHITECTURE §4 (`.claude/kit/`, `kit.toml`), §7 (one module, three entry points),
§8 (changelog fragments); decisions 8, 9, 13, 14

## Goal
A project can list forbidden patterns in `.claude/kit.toml` and have them enforced the same way
everywhere: right after an agent edits a file (Claude Code hook), on demand by a person or agent
(`kit check rules`), before each commit (git pre-commit), and in CI. The same CLI also compiles
changelog fragments into `CHANGELOG.md`.

## Out of scope
- Protected paths and the command backstop: plan 03 (it adds `kit check protected` to `check all`).
- Wiring hooks into `settings.json`, choosing the interpreter, enabling the git hook: plan 08.
- Lanes config (`[[lanes]]`) beyond tolerating the table: plan 04.
- The CI workflow file for installed projects: plan 09 (it calls `kit check all --diff`).

## Open questions
1. **How clever should comment stripping be?** *Recommendation:* line comments by file type
   (`#`, `//`, `--`) plus `/* */` and `<!-- -->` blocks; no string parsing. A comment marker inside
   a string (`"http://x"`) ends checking for that line, so the check can *miss* a violation there but
   never raises a false alarm. Document the limit; per-rule `ignore_comments = false` turns it off.
2. **Unknown keys in `kit.toml`?** *Recommendation:* an error in the CLI and CI (a typo like
   `pathes =` silently disabling a rule is worse than a loud failure); in hook mode, the same error
   is reported as a non-blocking hook error and the edit goes through (fail open, decision 9).
3. **Pre-commit:** *Recommendation:* ship a native `.githooks/pre-commit` (POSIX sh, which Git for
   Windows also runs) calling `kit check all --staged`; the installer enables it with
   `core.hooksPath` only after asking (plan 08). Support for the pre-commit framework is Later.

**Answers (owner, 2026-10-04):** all three as recommended. Decisions 23–25.

## Reuse
- `kitlib/render.py` (plan 01): pattern for small, strict, stdlib-only modules.
- `payload/templates/docs/changelog.d/README.md.tmpl`: the fragment format `changelog build` reads.
- First implementation's `check-code-rules.py` (survey): exit 2 on findings, ignore comments, fail
  open. Reference only.
- Claude Code hook protocol (checked 2026-10-04): PostToolUse input has `cwd`, `tool_name`,
  `tool_input.file_path`; exit 2 shows stderr to Claude (the edit already happened); any other
  non-zero exit is a visible, non-blocking "hook error".

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `payload/kit-owned/.claude/kit/cli.py` | New | `kit` entry point (argparse): `check rules\|all`, `hook rules-check`, `changelog build` |
| `.../kitlib/config.py` | New | Find the project root (git top level), load and validate `.claude/kit.toml`; `ConfigError` names file, key and problem |
| `.../kitlib/globs.py` | New | Gitignore-style glob matching (`**`, `*`, `?`, `[...]`), same results on Windows and POSIX paths |
| `.../kitlib/comments.py` | New | Strip comments by file extension (question 1) |
| `.../kitlib/findings.py` | New | `Finding(check, path, line, message)`; text output for people, one-line form for hook stderr |
| `.../kitlib/gitfiles.py` | New | Files to check: explicit list, `--staged` (reads the staged content, not the working tree), `--diff BASE` |
| `.../kitlib/rules_check.py` | New | Apply `[[checks.rules]]` (id, pattern, paths, optional exclude, message, ignore_comments) |
| `.../kitlib/changelog.py` | New | Compile `docs/changelog.d/*.md` (skipping `README.md`) into a dated release section, Keep a Changelog heading order; delete fragments; `--dry-run` |
| `payload/kit-owned/.githooks/pre-commit` | New | POSIX sh; runs `check all --staged`; exit non-zero blocks the commit |
| `payload/templates/.claude/kit.toml.tmpl` | New | `[project]` (name, test command, integration branch) and a commented example rule |
| `payload/placeholders.toml` | Edit | Nothing new expected; checked by the template tests |
| `tests/test_globs.py`, `test_comments.py`, `test_config.py`, `test_rules_check.py`, `test_cli.py`, `test_hook_rules_check.py`, `test_changelog.py`, `test_precommit.py` | New | See Tests |

Exit codes. **CLI:** 0 clean, 1 findings, 2 usage or config error. **Hook:** 0 clean or file not
covered, 2 findings (stderr to Claude), 1 kit error (visible, non-blocking).

## Steps
1. Tests then code: `globs`, `comments`, `findings` (pure functions, no I/O).
2. Tests then code: `config` (root discovery, validation, unknown-key errors).
3. Tests then code: `rules_check` over explicit files.
4. `cli.py`: `check rules FILES`, `check all`; exit codes; tests run it as a subprocess in a temp
   git repo whose path contains spaces.
5. `gitfiles` and `--staged` / `--diff BASE`; tests prove staged mode reads the staged blob.
6. Hook mode: `hook rules-check` reading recorded PostToolUse JSON; tests for clean, findings,
   uncovered file, deleted file, broken config (exit 1), missing config (exit 0, kit not set up).
7. `changelog build` and the `.githooks/pre-commit` script, with tests.
8. Review in a fresh context, fix findings, open the PR.

## Tests
| Test | Proves |
| --- | --- |
| `test_globs` | `**/`, `*` not crossing `/`, `?`, classes, Windows `\` paths normalized, anchoring to the root |
| `test_comments` | Each comment style stripped; a marker in a string can only cause a miss, never a false alarm |
| `test_config` | Root found from a subfolder; valid file loads; unknown key, wrong type, bad regex each give a `ConfigError` naming the key |
| `test_rules_check` | A match is reported with path and line; excluded and uncovered files ignored; comments ignored unless `ignore_comments = false` |
| `test_cli` | Exit 0/1/2 as specified; output lists every finding; works from a path with spaces |
| `test_cli::test_staged_reads_index_not_worktree` | A violation staged then fixed only in the working tree is still caught (and the reverse) |
| `test_hook_rules_check` | Exit 2 + findings on stderr; exit 0 for clean or uncovered; exit 1 with a clear message on a broken config; never a Python traceback |
| `test_changelog` | Fragments merged by heading in Keep a Changelog order, README skipped, fragments deleted, unknown heading rejected, `--dry-run` writes nothing |
| `test_precommit` | The script blocks a commit with a violation and allows a clean one (real `git commit` in a temp repo) |

## Done when
- [x] Tests above pass locally and in CI (Windows + Ubuntu, Python 3.11 + 3.13)
- [x] Reviewer report attached to the PR; every 🔴 fixed
- [x] CHANGELOG, ROADMAP, ARCHITECTURE §15 (answered questions) and decisions log updated

## Notes after implementation
Changes from the plan:
- **`check` with no files checks every tracked file** (`git ls-files`), so `kit check all` is a
  useful whole-project run; `--diff BASE` uses the merge base (`BASE...HEAD`), as a pull request
  sees it.
- **`.claude/kit/python-path`** (one line, written by the installer, gitignored) tells the
  pre-commit script which Python to run; it falls back to `python3`, then `python`.
- **Binary files are skipped** (a NUL byte in the first 8 KB).
- `test_templates.py` gained a test that the rendered `kit.toml` loads as a valid config.
- `test_findings.py` added for the output format.
- **From the review** (each fix has a test that fails on the old code, checked by running the new
  tests against the pre-fix code): UTF-8 output so non-ASCII findings can't crash a Windows
  console; staged submodules and symlinks skipped; a missing or folder argument is an error, not
  "clean"; a lone trailing-slash glob (`build/`) matches at any depth, like gitignore; empty or
  uncompilable globs, patterns and ids are config errors; files are filtered by rule coverage before
  being read (the hook and `check all` stay cheap in asset-heavy repos); UTF-8 byte-order marks
  accepted; a removed block comment leaves a space so tokens can't join; line numbers follow editor
  numbering; a hook-name typo is a non-blocking error; `changelog build` refuses when
  `[Unreleased]` already has entries.

Answered for later plans: hook commands on Windows run in Git Bash by default (PowerShell if Git
Bash is missing), and Claude Code's `args` form runs a program with no shell at all, which avoids
quoting problems with paths containing spaces. Plan 08 should use it.

New for plan 08: values rendered into `kit.toml` must be TOML-escaped (a test command containing
`"` would break the file).
