---
status: now
lane: any
size: S
---
# Strip CR from python-path in the pre-commit hook

`.githooks/pre-commit` read `.claude/kit/python-path` without `tr -d '\r'`, unlike
`.claude/kit/hook` and `.claude/kit/kit`. A python-path edited by hand on Windows ends in CRLF, and
on macOS/Linux the hook then runs `python3\r` and fails. Found in plan 08's review (PR 28).

**Done when:** the hook strips the `\r` like the launchers, and a test commits with a CRLF
python-path.

Done 2026-10-06: the hook pipes through `tr -d '\r'`; `test_crlf_python_path_still_finds_python`
in `tests/test_precommit.py`. Git for Windows' sh already drops the `\r` in `$(...)`, so the test
can only fail on macOS/Linux (the bug was reproduced and the fix checked under WSL Ubuntu).
