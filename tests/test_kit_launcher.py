"""`.claude/kit/parallanes`: how kit-owned skills run the kit CLI (decision 71).

Skills are kit-owned, so they can't hold `{{kit_command}}` or this machine's interpreter path; the
launcher takes Python from python-path, like the hook launcher (decision 57), but passes every exit
code through unchanged: these are commands, not guards.
"""

import shutil
import subprocess
import sys

import pytest

from helpers import ROOT, make_repo

LAUNCHER = ROOT / "payload" / "kit-owned" / ".claude" / "kit" / "parallanes"

needs_sh = pytest.mark.skipif(shutil.which("sh") is None, reason="needs sh (Git Bash on Windows)")


def install_kit(repo, python=sys.executable):
    kit = repo / ".claude" / "kit"
    shutil.copytree(
        LAUNCHER.parent, kit, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "python-path")
    )
    (kit / "python-path").write_text(str(python) + "\n", encoding="utf-8")
    return kit


def run(repo, *args):
    # The skills run it as `sh .claude/kit/parallanes ...` from the project root.
    return subprocess.run(["sh", ".claude/kit/parallanes", *args], cwd=repo, capture_output=True, text=True)


def test_launcher_has_lf_endings():
    assert b"\r\n" not in LAUNCHER.read_bytes()


@pytest.mark.slow
@needs_sh
def test_launcher_runs_a_kit_command_in_a_path_with_spaces(tmp_path):
    repo = make_repo(tmp_path)
    install_kit(repo)
    result = run(repo, "next", "--offline")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("Here: not a lane")


@pytest.mark.slow
@needs_sh
@pytest.mark.parametrize("code", [1, 2])
def test_launcher_passes_exit_codes_through(tmp_path, code):
    repo = make_repo(tmp_path)
    kit = install_kit(repo)
    (kit / "cli.py").write_text(f"import sys\nprint(sys.argv[1:])\nraise SystemExit({code})\n", encoding="utf-8")
    result = run(repo, "lanes", "finish", "--title", "a title with spaces")
    assert result.returncode == code
    assert "'a title with spaces'" in result.stdout  # arguments arrive intact


@pytest.mark.slow
@needs_sh
def test_launcher_without_python_says_so(tmp_path):
    repo = make_repo(tmp_path)
    install_kit(repo, python=tmp_path / "no-such-python")
    result = run(repo, "next")
    assert result.returncode == 2
    assert "python-path" in result.stderr


def test_lanes_get_this_machines_python_path():
    """python-path is gitignored, so a new lane only has it if .worktreeinclude copies it; without
    it both launchers fall back to `python3`, which on Windows may be the Store alias. Found in
    plan 07's live run."""
    lines = (ROOT / "payload" / "templates" / ".worktreeinclude.tmpl").read_text(encoding="utf-8").splitlines()
    assert ".claude/kit/python-path" in lines
