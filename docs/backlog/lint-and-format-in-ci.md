---
status: next
lane: any
size: M
---
# Lint and format the kit's own code in CI

Most modern Python repos run ruff (lint and format) and enforce it in CI and pre-commit; this one
doesn't yet (ROADMAP §14 lists it as Later). For a public showcase it's the most visible gap, and
it is cheap. Dev-only tooling, so the stdlib-only rule for installed files is unaffected.

**Done when:** `ruff check` and `ruff format --check` run in CI on every push and PR and pass; the
rule set and line length live in `pyproject.toml`; AGENTS.md says how to run them; ROADMAP §14
moves linting from Later to done. Also clears [wrap-long-lines](wrap-long-lines.md).
