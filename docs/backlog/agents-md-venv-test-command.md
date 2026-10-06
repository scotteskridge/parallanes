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
