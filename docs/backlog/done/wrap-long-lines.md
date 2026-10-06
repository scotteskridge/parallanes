---
status: later
lane: any
size: S
blocked_by: lint-and-format-in-ci
---
# Keep source lines to an agreed length

About 25 lines in the kit's source run past 120 characters, and nothing enforces a limit. The
formatter from [lint-and-format-in-ci](lint-and-format-in-ci.md) should settle this; this item
exists so it isn't forgotten if that one stops short of formatting.

**Done when:** a line length is set in `pyproject.toml` and no source or test line exceeds it.

Done 2026-10-06 with lint-and-format-in-ci (decision 94): line length 120, enforced by ruff in CI.
