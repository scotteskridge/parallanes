# 03 — Protected paths and commands

**Status:** In progress
**Branch / PR:** `plan/03-protected-paths`
**Builds on:** plan 02 (kitlib, `kit` CLI, hook mode); ARCHITECTURE §5, §7 (protected paths and
commands), §14; decisions 7 (manifest), 9 (fails closed), 14, 15 (deny rules primary, hook a backstop)

## Goal
A project lists paths and commands in `[protected]` in `.claude/kit.toml`, and the kit turns that
into protection: deny rules in `.claude/settings.json` (Claude Code enforces them), a PreToolUse
hook that catches forms deny rules miss, and `kit check protected` for pre-commit and CI. The docs
say plainly what none of this stops, and that the real gate is the server (CI, branch protection).

## Out of scope
- Wiring the hook into `settings.json`, the installer asking before touching an existing
  `settings.json`, and the full allow/deny template: plan 08 (it calls `kit settings sync`). Plan 08
  may fold the generated-rules record (question 3) into its manifest (decision 7).
- The CI workflow file: plan 09 (it runs `kit check all --diff`, which now includes `protected`).
  **Note for plan 09:** generate `CODEOWNERS` entries from `[protected].paths` and document branch
  protection (required review, no force-pushes). That's the industry-standard enforcement for
  protected paths; everything in this plan is local and guards against mistakes.
- The README's guarantees table: plan 12 (it links the doc this plan writes).
- Sandbox *configuration*: we recommend it; we don't generate it.

## Claude Code behaviour this relies on (docs, checked 2026-10-04)
- `Edit(/path)` in project settings anchors at the session's working directory (the worktree in a
  lane). A bare `Edit(vendor/**)` deny matches `vendor/` **at any depth**, so the kit always writes
  the `/` form. An `Edit` deny also blocks Write, NotebookEdit, and recognized shell writes (`sed`,
  `tee`, redirections). Coverage of PowerShell cmdlets (`Set-Content`, `Out-File`) is **not
  documented**.
- Deny rules can't be carved out: an allow rule never overrides a matching deny. A deny at any
  settings level wins over an allow at any other.
- `Bash(...)` deny rules apply to every subcommand (`&&`, `;`, `|`, subshells, `$(...)`, loop
  bodies), strip wrappers (`timeout`, `nohup`, bare `xargs`) and match past leading `FOO=bar`
  assignments. They do **not** match past options: `Bash(git push --force *)` misses
  `git -C . push --force` and `git push origin main --force`. `PowerShell(...)` rules exist and match
  case-insensitively.
- `bypassPermissions` skips permission prompts, so **ask rules don't hold in that mode**. Whether
  they prompt in `acceptEdits` mode isn't stated; the plan verifies it by hand and records the result.
- PreToolUse: **only exit 2 (or JSON `permissionDecision: "deny"`) blocks**; exit 1 lets the call
  through, and so does a hook timeout. A hook deny holds even in `bypassPermissions`. The hook input
  carries `cwd` and `permission_mode`. So "fails closed" means: every error path exits 2.

## Open questions
1. **What does the backstop hook watch?** *Recommendation:* `Bash|PowerShell` commands against
   `[protected].commands`; `Edit|Write|NotebookEdit` file paths against `[protected].paths` (exact,
   cheap, and still protects if `settings.json` drifted); and, because Windows comes first and has no
   sandbox, the target paths of common PowerShell write cmdlets (`Set-Content`, `Add-Content`,
   `Out-File`, `New-Item`, `Remove-Item`, `Move-Item`, `Copy-Item`, `Rename-Item`, and their aliases)
   from `-Path`/`-LiteralPath`/`-Destination` or the first positional argument. Documented as best
   effort. No guessing at write targets of arbitrary Bash or scripts (documented limit).
2. **How clever should command matching be?** It guards against mistakes, not adversaries, so keep
   it to the cheap cases. *Recommendation:* split on `&&`, `||`, `;`, `|`, newlines; tokenize (POSIX
   `shlex` for Bash, quotes and whitespace for PowerShell, case-insensitive); strip leading `FOO=bar`
   assignments, wrappers (`env`, `sudo`, `timeout`, `nohup`, `command`, `xargs`) and git global
   options (`-C x`, `-c k=v`, `--git-dir=`, `--work-tree=`, `--no-pager`). A protected command
   matches when program and subcommand match and **every other pattern token appears somewhere** in
   the arguments, order-free, with short-flag clusters expanded (`-xdf` contains `-f`). So
   `git push origin main --force` and `git clean -xdf` are caught; `--force-with-lease` is not (the
   safe form). Known misses, documented, not chased: `git push origin +main`, git aliases, scripts,
   commands inside `bash -c "..."` strings or `$(...)`.
3. **How does `kit settings sync` tell its rules from the owner's?** JSON has no comments.
   *Recommendation:* sync only **adds** missing rules and removes rules it wrote before, listed in
   `.claude/kit/generated-rules.json` (committed, kit-owned). Owner rules are never touched.
   `kit check settings` fails when an expected rule is missing or a recorded rule is stale.
   `--dry-run` prints the change. (A marker key inside `settings.json` risks settings validation.)
4. **Protecting the kit's own config** (`/.claude/settings.json`, `/.claude/kit.toml`,
   `/.claude/kit/**`, `/.githooks/**`). An agent that edits these can switch protection off, but
   `/onboard` (plan 07) must write `kit.toml`. Deny rules can't be approved case by case; ask rules
   can, but vanish in `bypassPermissions`; a hook deny holds everywhere but would block `/onboard`.
   *Recommendation:* **ask rules, plus the hook denies edits to these paths only when
   `permission_mode` is `bypassPermissions`** (no human is there to answer the ask). The doc tells
   owners who want more to set `permissions.disableBypassPermissionsMode`. On by default;
   `[protected] guard_kit = false` turns both off.
5. **Secrets.** ARCHITECTURE §5 lists secrets under deny rules, but `[protected]` has no key.
   *Recommendation:* add `[protected].secrets` → `Read(...)` and `Edit(...)` deny rules (bare names,
   so they match at any depth). Since a deny can't be carved out, the default names files rather than
   `.env.*` (which would block the committed `.env.example`): `[".env", ".env.local", ".env.*.local"]`.
   The template comment tells projects to add their own (`.env.production`, key files).
6. **A human changing a protected path on purpose.** *Recommendation:* `kit check protected` reports
   it (exit 1); the local escape is `KIT_ALLOW_PROTECTED=1` on the commit; how a PR declares it
   (label, trailer, `CODEOWNERS` review) is plan 09's call.
7. **Missing or broken config in the hook.** *Recommendation:* the hook finds the project root from
   the input's `cwd`, so a lane uses its own worktree's `kit.toml`. No `kit.toml` → allow (kit not set
   up there); a `kit.toml` that fails to load, bad stdin JSON, or any crash → block (exit 2) saying
   what to fix (decision 9).
8. **The agent switching off the local checks itself.** It could set `KIT_ALLOW_PROTECTED=1` or run
   `git commit --no-verify`. *Recommendation:* the default `[protected].commands` include
   `git commit --no-verify` and `git commit -n` (the cluster rule catches `-nm`); the hook blocks any
   command that sets `KIT_ALLOW_PROTECTED` (it's for humans at a terminal) or changes
   `core.hooksPath`. The doc states that the local checks are a convenience and CI is the gate.

**Answers (owner, 2026-10-04):** all eight as recommended. Decisions 27–34.

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
| `.../kitlib/commands.py` | New | Split, tokenize, strip assignments, wrappers and git global options, match (question 2); PowerShell write targets (question 1) |
| `.../kitlib/protected.py` | New | `check(paths)` → findings; `check_command(text, shell)`; `check_tool_call(json)` for the hook (questions 1, 4, 8) |
| `.../kitlib/settings.py` | New | Expected deny and ask rules; read/merge/write `settings.json` (LF, 2-space, key order kept); generated-rules record |
| `payload/kit-owned/.claude/kit/cli.py` | Edit | `check protected`, `check settings`, `settings sync [--dry-run]`, `hook protected` |
| `payload/templates/.claude/kit.toml.tmpl` | Edit | `[protected]` with default commands and secrets, commented paths example |
| `payload/templates/docs/ai/protected-paths.md.tmpl` | New | What each layer stops and misses; sandbox on macOS/Linux/WSL2 and the Windows gap; CI, `CODEOWNERS` and branch protection as the real gate; `disableBypassPermissionsMode` |
| `payload/templates/docs/ai/WORKFLOW.md.tmpl` | Edit | Link the new doc from its guarantees table |
| `tests/test_commands.py`, `test_protected.py`, `test_settings.py`, `test_hook_protected.py`, `test_cli.py` | New / Edit | See Tests |

Exit codes. **CLI:** as plan 02 (0 / 1 / 2). **Hook:** 0 allow; 2 block, with the reason on stderr,
for a match *and* for every error (question 7). Must stay well under 1 s.

## Steps
1. Tests then code: `[protected]` config validation.
2. Tests then code: `commands.py` (a table of command strings → match / no match, both shells).
3. Tests then code: `protected.py` path and command checks; `check protected` in the CLI and `check all`.
4. Tests then code: `hook protected` on recorded PreToolUse JSON (Bash, PowerShell, Edit, Write,
   each permission mode).
5. Tests then code: `settings.py`, `settings sync`, `check settings` on temp projects with and
   without an existing `settings.json`.
6. Template and doc changes; template tests render them. Check by hand in a real session whether an
   ask rule prompts in `acceptEdits` mode; record it in the doc.
7. Fresh-context review, fix findings with tests, open the PR.

## Tests
| Test | Proves |
| --- | --- |
| `test_config` (added) | Valid `[protected]` loads; unknown key, wrong type, bad glob, empty command each name the key |
| `test_commands` | Caught: reordered flags, `-C`/`-c`, extra spaces, quotes, `&&`/`;`/`|`, `FOO=bar` prefixes, wrappers, flag clusters, PowerShell casing, `git commit -nm x`. Allowed: `--force-with-lease`, plain `git push`, look-alikes (`git pushx`). PowerShell write targets found by named and positional argument and alias |
| `test_protected` | Path findings for protected files only; Windows `\` paths; staged and diff modes; `KIT_ALLOW_PROTECTED=1` |
| `test_hook_protected` | Blocks with exit 2 and a clear reason; allows clean calls; kit-config edits blocked only in `bypassPermissions`; commands setting `KIT_ALLOW_PROTECTED` or `core.hooksPath` blocked; root found from `cwd` (two worktrees, different `kit.toml`); exit 2 on broken config, bad JSON, injected crash; exit 0 with no `kit.toml`; never a traceback; path with spaces |
| `test_settings` | Paths `/`-anchored, secrets bare, kit-config ask rules (absent with `guard_kit = false`); sync adds, removes only recorded rules, keeps owner rules and other keys; idempotent; `--dry-run` writes nothing; `check settings` flags missing and stale rules; LF output |
| `test_templates` (added) | Rendered `kit.toml` loads; its default secrets don't match `.env.example` |

## Done when
- [ ] Tests above pass locally and in CI (Windows + Ubuntu, Python 3.11 + 3.13)
- [ ] Reviewer report attached to the PR; every 🔴 fixed
- [ ] CHANGELOG, ROADMAP, ARCHITECTURE §7 and §15 (incl. the plan 09 note), decisions log updated

## Notes after implementation
Changes from the plan:
- **The hook also reads common Bash file commands** (`rm`, `rmdir`, `mv`, `cp`, `touch`,
  `truncate`, `ln`), not only PowerShell cmdlets. Question 1 said no guessing for Bash, but on
  Windows the Bash tool runs Git Bash with no sandbox, and deny rules don't cover `rm` or `mv`, so
  the same reasoning applies. Parsing lives in `kitlib/file_commands.py` (split out of
  `commands.py` past 300 lines).
- **Deleting a folder that holds a protected path is blocked** (`rm -rf src` when `src/vendor/**` is
  protected), for patterns with a folder in them. Found while writing the limits doc; writes into a
  folder (`cp x src`) are not affected.
- **Default `git clean -f`, not `-fdx`:** every flag in a pattern must be present, and `git clean
  -fd` destroys too.
- **A mistyped hook name fails closed in PreToolUse** (the input's `hook_event_name` tells the CLI
  which event it is); in PostToolUse it stays a non-blocking error.
- **`check all` includes `settings`**, so pre-commit and CI catch a `kit.toml` change that wasn't
  synced. Test repos now get synced settings, as an installed project has.
- **`MultiEdit`** is covered with the other file tools.
- **Not done:** step 6's check of ask rules in `acceptEdits` mode. The headless `claude -p` run
  failed (CLI not logged in); the doc says "not yet verified" and ARCHITECTURE §15 carries it.

