# Live checks

Unit tests prove the kit's code; a live check proves Claude Code actually runs it the way the kit
assumes: that a hook fires, a skill loads, a permission rule holds. Each one runs real headless
`claude -p` sessions in a scratch project, so it costs money and needs your login. That's why live
checks never run in CI or in the normal test commands: without `--live` they are skipped, whatever
`-m` says. Run them with the project's `.venv` (`.venv/bin/python` on macOS/Linux; AGENTS.md):

```bash
.venv/Scripts/python -m pytest --live tests/live
```

## Why each check asserts what loaded

`--bare` "will become the default for `-p` in a future release"
([headless](https://code.claude.com/docs/en/headless.md)). It skips hooks, skills, subagents,
plugins and `CLAUDE.md`, and there is no flag to opt out of it. A live check that only passed the
right flags would then go on passing while testing nothing. So every check goes through
`tests/live/claude_run.py`, which:

- **States what loads:** `--setting-sources project,local` keeps your personal `~/.claude`
  settings, hooks, plugins and skills out of the result (a personal skill was absent from a pinned
  run's `system/init`, Claude Code 2.1.291); `--permission-mode` and `--model` are always
  passed; `--max-budget-usd` caps each run (1 USD unless a check says otherwise).
- **Asserts it from the stream:** `--output-format stream-json --verbose --include-hook-events`.
  Skills, agents and plugins must be listed in the `system/init` event; hooks must show a
  `hook_started` event, because `system/init` doesn't list hooks (checked with Claude Code 2.1.291).
  If something is missing, the check fails and says what, before any of its own assertions run.
  Name a hook as the stream does (`PreToolUse:Edit`). This shows the session wasn't stripped down,
  not which file the hook came from: a check that relies on one particular hook needs a canary
  with an effect of its own.
- **Requires a finished run:** the last event must be a `success` result. A run stopped by the
  budget or the turn cap, or by an API error, fails the check, unless it passes `expect_error=True`.
- **Checks trust when it matters:** agent frontmatter hooks, such as the reviewer's read-only guard,
  are skipped in a folder Claude Code doesn't trust, and `-p` shows no trust dialog. A check that
  needs them passes `needs_trust=True`. Each check reuses a fixed folder under your temp folder
  (`kit-live/<check>`), so you accept its trust dialog once: open Claude Code in exactly that
  folder and accept (trust on a folder above it doesn't count, since that isn't shown to carry
  down). The helper only reads `~/.claude.json` (or `$CLAUDE_CONFIG_DIR/.claude.json`) to see
  whether you have; the kit never writes it.

On Windows the helper needs the native `claude` install: a `claude.cmd` shim runs through cmd.exe,
which cuts a prompt at a newline and mangles `%` and quotes, so it is refused.

Built-in plugins that ship with Claude Code still load; `system/init` lists them.

## Writing one

Put it in `tests/live/test_<what>.py` with `pytestmark = pytest.mark.live`. Use
`scratch_project("<name>")` for its folder (one per test, since tests run in parallel), write the
files the check needs, then call `run_claude(...)` with the `expect_skills`, `expect_agents`,
`expect_plugins` or `expect_hooks` it relies on. Build a canary into the project: a deny rule or a
hook that must take effect, so a session that silently loaded nothing can't pass. Assert on files
and on `run.denied_paths()`, not on what Claude says it did.

| Check | Proves |
| --- | --- |
| `test_ask_rules.py` | Ask rules are never auto-approved in `bypassPermissions` or `acceptEdits`; a control run without the rule edits the file (decision 92) |
| `test_installed_kit.py` | A project set up by the installer has its hooks firing from `settings.json` (SessionStart, PreToolUse on Edit and Bash, PostToolUse), the protected hook blocking a `cp` into a protected folder, and the generated deny rule refusing a Write (plan 08) |

Earlier live checks (plans 03–07b) were run by hand and are recorded in their plans' notes. Later
live checks use this helper. Plan 11's evals design their own harness, but follow the same rules
(decision 93): stream-json output, pinned settings, and asserting what loaded.
