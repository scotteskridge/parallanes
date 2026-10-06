"""Repo-level checks that keep the kit honest before any feature code exists."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_python_meets_minimum_version():
    # Hooks and configs rely on tomllib, added in 3.11.
    assert sys.version_info >= (3, 11)


def test_claude_md_imports_agents_md():
    # CLAUDE.md must pull in the cross-tool rules rather than duplicate them.
    claude_md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude_md.splitlines()[0].strip() == "@AGENTS.md"


def test_text_files_are_committed_with_lf_endings():
    # The working tree may use CRLF on Windows checkouts without eol=lf; .gitattributes forces LF.
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "* text=auto eol=lf" in attributes


def test_ruff_is_pinned_and_ci_runs_both_checks():
    # Decision 94: an unpinned ruff can reformat differently from CI; a dropped command lets drift in.
    import re
    import tomllib

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev = project["project"]["optional-dependencies"]["dev"]
    pins = [d for d in dev if re.fullmatch(r"ruff==\d+\.\d+\.\d+", d)]
    assert len(pins) == 1, dev
    assert project["tool"]["ruff"]["line-length"] == 120
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert f'pip install "{pins[0]}"' in workflow
    assert "ruff check" in workflow
    assert "ruff format --check" in workflow
