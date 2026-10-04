# 03 — Protected paths and commands

**Status:** Draft
**Branch / PR:** `plan/03-protected-paths`
**Builds on:** plan 02 (kitlib, `kit` CLI, hook mode); ARCHITECTURE §5, §7 (protected paths and
commands), §14; decisions 9 (fails closed), 14, 15 (deny rules primary, hook a backstop)

## Goal
A project lists paths and commands in `[protected]` in `.claude/kit.toml`, and the kit turns that
into protection: deny rules in `.claude/settings.json` (Claude Code enforces them), a PreToolUse
hook that catches command forms deny rules miss, and `kit check protected` for pre-commit and CI.
The docs say plainly what none of this stops.

## Out of scope
- Wiring the hook into `settings.json`, the installer asking before touching an existing
  `settings.json`, and the full allow/deny template: plan 08 (it calls `kit settings sync`).
- The CI workflow file: plan 09 (it runs `kit check all --diff`, which now includes `protected`).
- The README's guarantees table: plan 12 (it links the doc this plan writes).
- Sandbox *configuration*: we recommend it; we don't generate it.

## Claude Code behaviour this relies on (docs, checked 2026-10-04)
- `Edit(/path)` in project settings anchors at the session's working directory (the worktree in a
  lane). A bare `Edit(vendor/**)` deny matches `vendor/` **at any depth**, so the kit always writes
  the `/` form. An `Edit` deny also blocks Write, NotebookEdit, and recognized shell writes (`sed`,
  `tee`, redirections). Coverage of PowerShell cmdlets (`Set-Content`, `Out-File`) is **not
  documented**.
- `Bash(...)` rules split compound commands (`&&`, `;`, `|`) and strip a few wrappers (`timeout`,
  `nohup`, bare `xargs`), but do **not** match past options: `Bash(git push --force *)` misses
  `git -C . push --force` and `git push origin main --force`. `PowerShell(...)` rules exist and match
  case-insensitively.
- A deny at any settings level can't be overridden by an allow at another.
- PreToolUse: **only exit 2 (or JSON `permissionDecision: "deny"`) blocks**; exit 1 lets the call
  through, and so does a hook timeout. A hook deny holds even in `bypassPermissions` mode. So
  "fails closed" means: every error path exits 2.

## Open questions
1. **What does the backstop hook watch?** *Recommendation:* `Bash|PowerShell` commands against
   `[protected].commands` (as designed), **plus** `Edit|Write|NotebookEdit` file paths against
   `[protected].paths`. The path check is exact and cheap, and it still protects when
   `settings.json` has drifted or a user's settings were edited by hand. No guessing at write targets
   inside shell commands (documented limit instead).
2. **How does command matching work?** *Recommendation:* split on `&&`, `||`, `;`, `|`, newlines and
   `$(`/backticks; tokenize (POSIX `shlex` for Bash, whitespace and quotes for PowerShell,
   case-insensitive); strip wrappers (`env`, `sudo`, `timeout`, `nohup`, `command`, `xargs`) and git
   global options (`-C x`, `-c k=v`, `--git-dir=`, `--work-tree=`, `--no-pager`). A protected command
   matches when the program and subcommand match and **every remaining token of the pattern appears
   somewhere** in the arguments, order-free; short-flag clusters expand (`-xdf` contains `-f`, `-d`,
   `-x`). So `git push origin main --force` and `git clean -xdf` are caught; `--force-with-lease` is
   not (it's the safe form). Known misses, documented: `git push origin +main`, aliases, scripts,
   `bash -c "..."` strings (we recurse into `bash -c`/`sh -c`/`pwsh -c` one level; deeper is a miss).
3. **How does `kit settings sync` tell its rules from the owner's?** JSON has no comments.
   *Recommendation:* sync only ever **adds** missing rules and removes rules it wrote before, listed
   in `.claude/kit/generated-rules.json` (committed, kit-owned). Owner-written rules are never
   touched. `kit check settings` fails when an expected rule is missing or a recorded rule is stale.
   `--dry-run` prints the change. (The alternative, a marker key inside `settings.json`, risks Claude
   Code's settings validation.)
4. **Protecting the kit's own config.** An agent that can edit `kit.toml` or `settings.json` can
   switch the protection off. But `/onboard` (plan 07) must write `kit.toml`, and deny rules can't be
   approved case by case. *Recommendation:* generate **ask** rules (not deny) for
   `/.claude/settings.json`, `/.claude/kit.toml`, `/.claude/kit/**`, `/.githooks/**`, so every change
   needs the owner's click, even in accept-edits mode. On by default; `[protected] guard_kit = false`
   turns it off.
5. **Secrets.** ARCHITECTURE §5 lists "secrets" under deny rules, but `[protected]` has no key for
   them. *Recommendation:* add `[protected].secrets` (default `[".env", ".env.*"]`, bare names so they
   match at any depth) → `Read(...)` and `Edit(...)` deny rules. Same generator, small addition.
6. **What does `kit check protected` (pre-commit, CI) do when a human changes a protected path on
   purpose?** *Recommendation:* it's a finding (exit 1), and the escape is explicit:
   `KIT_ALLOW_PROTECTED=1` for a local commit; how a PR declares it (label or trailer) is plan 09's
   call. Commands aren't checked here: there is nothing to check in a diff.
7. **Missing or broken config in the hook.** *Recommendation:* no `kit.toml` → allow (the kit isn't
   set up there); a `kit.toml` that fails to load, bad stdin JSON, or any crash → block (exit 2) with
   a message saying what to fix. This is decision 9's "fails closed".

## Reuse
- `kitlib/config.py`: already accepts the `protected` table; this plan validates its keys.
- `kitlib/globs.py` (`normalize`, `validate`, `matches_any`): path matching, Windows separators.
- `kitlib/gitfiles.py` (`staged`, `changed_since`, `tracked`) and `findings.py`: `check protected`.
- `cli.py`: `CHECKS` map (its comment already reserves `"protected"`), `run_hook` pattern, exit codes.
- `tests/helpers.py`, `test_hook_rules_check.py`: recorded hook JSON and temp repos with spaces.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `payload/kit-owned/.claude/kit/kitlib/config.py` | Edit | `Protected(paths, commands, secrets, guard_kit)`; validation with key-naming errors |
| `.../kitlib/commands.py` | New | Split, tokenize, strip wrappers and git global options, match (question 2) |
| `.../kitlib/protected.py` | New | `check(paths)` → findings; `check_command(text, shell)`; `check_tool_call(json)` for the hook |
| `.../kitlib/settings.py` | New | Expected rules from `[protected]`; read/merge/write `settings.json` (LF, 2-space, key order kept); generated-rules record |
| `payload/kit-owned/.claude/kit/cli.py` | Edit | `check protected`, `check settings`, `settings sync [--dry-run]`, `hook protected` |
| `payload/templates/.claude/kit.toml.tmpl` | Edit | `[protected]` with the default commands and secrets, commented paths example |
| `payload/templates/docs/ai/protected-paths.md.tmpl` | New | What each layer stops, what it doesn't, sandbox on macOS/Linux/WSL2, the Windows gap |
| `payload/templates/docs/ai/WORKFLOW.md.tmpl` | Edit | Link the new doc from its guarantees table |
| `tests/test_commands.py`, `test_protected.py`, `test_settings.py`, `test_hook_protected.py`, `test_cli.py` | New / Edit | See Tests |

Exit codes. **CLI:** as plan 02 (0 / 1 / 2). **Hook:** 0 allow; 2 block, with the reason on stderr,
for a match *and* for every error (question 7). Must stay well under 1 s.

## Steps
1. Tests then code: `[protected]` config validation.
2. Tests then code: `commands.py` (a table of command strings → match / no match, both shells).
3. Tests then code: `protected.py` path and command checks; `check protected` in the CLI and `check all`.
4. Tests then code: `hook protected` on recorded PreToolUse JSON (Bash, PowerShell, Edit, Write).
5. Tests then code: `settings.py`, `settings sync`, `check settings` on temp projects with and
   without an existing `settings.json`.
6. Template and doc changes; template tests render them.
7. Fresh-context review, fix findings with tests, open the PR.

## Tests
| Test | Proves |
| --- | --- |
| `test_config` (added) | Valid `[protected]` loads; unknown key, wrong type, bad glob, empty command each name the key |
| `test_commands` | Each form in question 2 caught: reordered flags, `-C`/`-c`, extra spaces, quotes, `&&`/`;`/`|`, wrappers, flag clusters, `bash -c`, PowerShell casing; `--force-with-lease`, `git push` and look-alikes (`git pushx`) allowed |
| `test_protected` | Path findings for protected files only; Windows `\` paths; staged and diff modes; `KIT_ALLOW_PROTECTED=1` |
| `test_hook_protected` | Blocks with exit 2 and a clear reason; allows clean calls; exit 2 on broken config, bad JSON and an injected crash; exit 0 with no `kit.toml`; never a traceback; runs from a path with spaces |
| `test_settings` | Rules are `/`-anchored, secrets bare; sync adds, removes only recorded rules, keeps owner rules and every other key; idempotent; `--dry-run` writes nothing; `check settings` flags missing and stale rules; output is LF |
| `test_templates` (added) | Rendered `kit.toml` loads and its `[protected]` generates the expected rules |

## Done when
- [ ] Tests above pass locally and in CI (Windows + Ubuntu, Python 3.11 + 3.13)
- [ ] Reviewer report attached to the PR; every 🔴 fixed
- [ ] CHANGELOG, ROADMAP, ARCHITECTURE §7 and §15, and decisions log updated

## Notes after implementation
<!-- Filled in at wrap-up: what changed from the plan and why. -->
