---
status: now
lane: any
size: S
---
# Make the documented dev install work again

`.venv/Scripts/python -m pip install -e ".[dev]"`, the setup command AGENTS.md documents, fails on a
fresh venv since plan 08 added the top-level `installer/` package: setuptools' flat-layout
discovery finds `payload` and `installer` and refuses to guess. CI didn't notice because it
installed pytest directly.

**Done when:** the documented command succeeds on a fresh venv, and CI installs the same way so
it can't silently break again.

Done 2026-10-06: `pyproject.toml` lists no packages (`[tool.setuptools] packages = []`), since the
kit isn't distributed as one, and declares its `[build-system]` instead of relying on pip's legacy
fallback; the CI pytest jobs install with `pip install -e ".[dev]"`, kept so by
a test in `tests/test_repo_basics.py`.
