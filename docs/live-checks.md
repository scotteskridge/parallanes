# Live checks

Unit tests prove the kit's code; a live check proves Claude Code actually runs it the way the kit
assumes: that a hook fires, a skill loads, a permission rule holds. Each one runs real headless
`claude -p` sessions in a scratch project, so it costs money and needs your login. That's why live
checks never run in CI or in the normal test commands.

```bash
python -m pytest -m live tests/live
```

## Why each check asserts what loaded

`--bare` "will become the default for `-p` in a future release"
([headless](https://code.claude.com/docs/en/headless.md)). It skips hooks, skills, subagents,
plugins and `CLAUDE.md`, and there is no flag to opt out of it. A live check that only passed the
right flags would then go on passing while testing nothing. So every check goes through
`tests/live/claude_run.py`, which:

- **States what loads:** `--setting-sources project,local` keeps your personal `~/.claude`
  settings, hooks and plugins out of the result; `--permission-mode` and `--model` are always
  passed; `--max-budget-usd` caps each run (1 USD unless a check says otherwise).
- **Asserts it from the stream:** `--output-format stream-json --verbose --include-hook-events`.
  Skills, agents and plugins must be listed in the `system/init` event; hooks must show a
  `hook_started` event, because `system/init` doesn't list hooks (checked with Claude Code 2.1.291).
  If something is missing, the check fails and says what, before any of its own assertions run.
- **Checks trust when it matters:** agent frontmatter hooks, such as the reviewer's read-only guard,
  are skipped in a folder Claude Code doesn't trust, and `-p` shows no trust dialog. A check that
  needs them passes `needs_trust=True`. Each check reuses a fixed folder under your temp folder
  (`kit-live/<check>`), so you accept its trust dialog once: open Claude Code there and accept.
  The helper only reads `~/.claude.json` to see whether you have; the kit never writes it.

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

Earlier live checks (plans 03–07b) were run by hand and are recorded in their plans' notes; plan
11's evals and later checks use this helper.
