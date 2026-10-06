---
status: later
lane: any
size: M
blocked_by: complete-type-hints
---
# Type-check the kit in CI

A type checker (mypy or pyright) is standard for Python code of this size, and it catches the
kind of wrong-shape bug the strict config validation guards against at runtime. Which checker is
an open design question: flag it, don't settle it silently.

**Done when:** the chosen checker runs in CI over `payload/kit-owned/.claude/kit/` on Python 3.11
and passes, with its settings in `pyproject.toml`, and the choice is recorded in the decisions log.
