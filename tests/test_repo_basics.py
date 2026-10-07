"""Repo-level checks that keep the kit honest before any feature code exists."""

import re
import sys
import tomllib
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
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev = project["project"]["optional-dependencies"]["dev"]
    pins = [d for d in dev if re.fullmatch(r"ruff==\d+\.\d+\.\d+", d)]
    assert len(pins) == 1, dev
    assert project["tool"]["ruff"]["line-length"] == 120
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert f'pip install "{pins[0]}"' in workflow
    # Whole step lines, so a commented-out step doesn't count.
    assert re.search(r"^\s*- run: ruff check \.$", workflow, re.M)
    assert re.search(r"^\s*- run: ruff format --check \.$", workflow, re.M)


def test_ci_installs_with_the_setup_command_agents_md_documents():
    # A pyproject.toml change once broke `pip install -e ".[dev]"` unnoticed, because CI installed
    # pytest directly; installing the documented way makes every pytest job check that command.
    command = 'python -m pip install -e ".[dev]"'
    assert command in (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    # A whole step line, so a commented-out step doesn't count.
    assert re.search(r"^\s*- run: " + re.escape(command) + "$", workflow, re.M)


def test_ci_cancels_superseded_pr_runs_but_never_main_runs():
    # Decision 95. A PR's runs share a group, so a new push cancels the older run. Each push to main
    # gets a group of its own (its run id): in a shared group GitHub keeps only one pending run and
    # cancels the rest, even with cancel-in-progress off, so back-to-back merges would lose results.
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    block = (
        "concurrency:\n"
        "  group: ${{ github.workflow }}-${{ github.event_name == 'pull_request' && github.ref || github.run_id }}\n"
        "  cancel-in-progress: ${{ github.event_name == 'pull_request' }}\n"
    )
    # Whole lines in order, so a commented-out copy or a job-level block doesn't count.
    assert re.search("^" + re.escape(block), workflow, re.M)
