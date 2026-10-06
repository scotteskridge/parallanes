---
status: now
lane: any
size: S
---
# Say in AGENTS.md which Python runs the tests

AGENTS.md says `python -m pytest`, but on the owner's machine the `python` on PATH has no pytest;
only `.venv` does. An agent following the rule gets "No module named pytest", and in a pipeline
(`| tail`) that failure can pass as exit 0.

**Done when:** AGENTS.md says to use the project's `.venv` (or activate it first) for the test
commands. AGENTS.md changes need the owner's OK on the exact lines first (CLAUDE.md).

Done 2026-10-06: AGENTS.md names `.venv/Scripts/python` (`.venv/bin/python` on macOS/Linux) for
pytest and ruff, and warns that piping test output through `tail` hides a failing exit code.
`docs/live-checks.md`, `pyproject.toml` and two test docstrings now say the same.
