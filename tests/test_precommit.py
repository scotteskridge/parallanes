"""The git pre-commit hook blocks a commit with a violation and lets a clean one through."""

import shutil
import stat
import subprocess
import sys

from helpers import ROOT, git, make_repo, write

KIT_OWNED = ROOT / "payload" / "kit-owned"


def install_hook(repo):
    shutil.copytree(KIT_OWNED / ".claude" / "kit", repo / ".claude" / "kit", dirs_exist_ok=True)
    shutil.copytree(KIT_OWNED / ".githooks", repo / ".githooks")
    hook = repo / ".githooks" / "pre-commit"
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    # What the installer will do: record the interpreter, point git at the hooks folder.
    write(repo, ".claude/kit/python-path", sys.executable + "\n")
    git(repo, "config", "core.hooksPath", ".githooks")


def commit(repo):
    return subprocess.run(["git", "commit", "-q", "-m", "test"], cwd=repo, capture_output=True, text=True)


def test_commit_with_a_violation_is_blocked(tmp_path):
    repo = make_repo(tmp_path)
    install_hook(repo)
    write(repo, "src/app.py", "print(1)\n")
    git(repo, "add", "src/app.py", ".claude/kit.toml")
    result = commit(repo)
    assert result.returncode != 0
    assert "src/app.py:1" in result.stdout + result.stderr
    assert git(repo, "log", "--oneline", "--all") == ""  # nothing was committed


def test_clean_commit_goes_through(tmp_path):
    repo = make_repo(tmp_path)
    install_hook(repo)
    write(repo, "src/app.py", "x = 1\n")
    git(repo, "add", "src/app.py", ".claude/kit.toml")
    result = commit(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_crlf_python_path_still_finds_python(tmp_path):
    # Edited by hand on Windows, python-path ends in CRLF; a kept \r makes the interpreter path wrong.
    # Git for Windows' sh drops the \r in $(...) by itself, so only macOS/Linux can catch a regression.
    repo = make_repo(tmp_path)
    install_hook(repo)
    (repo / ".claude" / "kit" / "python-path").write_bytes(sys.executable.encode() + b"\r\n")
    write(repo, "src/app.py", "x = 1\n")
    git(repo, "add", "src/app.py", ".claude/kit.toml")
    result = commit(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_hook_script_has_lf_endings():
    # A CRLF shebang line breaks sh on every platform.
    assert b"\r\n" not in (KIT_OWNED / ".githooks" / "pre-commit").read_bytes()
