"""The reviewer's read-only Bash guard (decision 57): only read-only git commands get through.

It sits in the reviewer agent's own frontmatter as a PreToolUse hook. In PreToolUse only exit 2
blocks; exit 1 and timeouts let the call through, so every error path must exit 2.
"""
import json
import shutil
import subprocess
import sys

import pytest

from helpers import ROOT, run_cli
from kitlib import reviewer_hook

ALLOWED = [
    "git diff",
    "git diff main...HEAD",
    "git diff --stat abc123",
    "git -C \"D:/my project/lane\" diff --name-only main...HEAD",
    "git --no-pager log --oneline -5",
    "git log -p -- \"src/a file.py\"",
    "git show HEAD:docs/plan.md",
    "git status --short",
    "git merge-base main HEAD",
    "git rev-parse --abbrev-ref HEAD",
    "git ls-files --others --exclude-standard",
    "git ls-files -o",
    "git blame -L 10,20 src/app.py",
    "git grep -n TODO",
    "git rev-list --count main..HEAD",
    "git cat-file -p HEAD",
    "git diff --output-indicator-new=+",
    "/usr/bin/git diff",
    "git diff && git status",
    "git diff\ngit log -1",
]

BLOCKED = [
    "git checkout main",
    "git switch -c x",
    "git commit -m x",
    "git stash",
    "git reset --hard",
    "git branch -D x",
    "git push",
    "rm -rf src",
    "python -m pytest",
    "ls",
    "git diff; rm x",
    "git diff && git checkout .",
    "git log | head -5",
    "git diff $(rm x)",
    "git diff `rm x`",
    "git diff > out.txt",
    "git diff --output=out.txt",
    "git diff --output out.txt",
    "git log --outp=out.txt",
    "git diff --ext-diff",
    "git grep -O TODO",
    "git grep --open-files-in-pager TODO",
    "git -c diff.external=evil diff",
    "git --exec-path=/tmp diff",
    "git --git-dir=/elsewhere/.git log",
    "GIT_PAGER=evil git log",
    "env GIT_EXTERNAL_DIFF=evil git diff",
    "git",
    "",
]


@pytest.mark.parametrize("command", ALLOWED)
def test_read_only_git_is_allowed(command):
    assert reviewer_hook.reason(command) is None


@pytest.mark.parametrize("command", BLOCKED)
def test_everything_else_is_blocked(command):
    assert reviewer_hook.reason(command)


def pre_tool_use(cwd, tool, tool_input):
    return json.dumps({
        "session_id": "test",
        "cwd": str(cwd),
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": tool_input,
    })


@pytest.mark.slow
def test_hook_blocks_with_exit_2_and_says_why(tmp_path):
    result = run_cli(tmp_path, "hook", "reviewer-bash", stdin=pre_tool_use(tmp_path, "Bash", {"command": "git commit -m x"}))
    assert result.returncode == 2
    assert "read-only" in result.stderr
    assert "git with one of" in result.stderr and " diff," in result.stderr  # says what is allowed


@pytest.mark.slow
def test_hook_allows_read_only_git(tmp_path):
    result = run_cli(tmp_path, "hook", "reviewer-bash", stdin=pre_tool_use(tmp_path, "Bash", {"command": "git diff"}))
    assert (result.returncode, result.stderr) == (0, "")


@pytest.mark.slow
@pytest.mark.parametrize("stdin", ["not json", "[]", json.dumps({"tool_name": "Bash", "tool_input": {}})])
def test_hook_fails_closed_on_bad_input(tmp_path, stdin):
    result = run_cli(tmp_path, "hook", "reviewer-bash", stdin=stdin)
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


@pytest.mark.slow
def test_hook_leaves_other_tools_alone(tmp_path):
    """The agent's matcher is Bash; another tool reaching the hook isn't this guard's business."""
    result = run_cli(tmp_path, "hook", "reviewer-bash", stdin=pre_tool_use(tmp_path, "Read", {"file_path": "x"}))
    assert result.returncode == 0


LAUNCHER = ROOT / "payload" / "kit-owned" / ".claude" / "kit" / "hook"


def test_launcher_has_lf_endings():
    assert b"\r\n" not in LAUNCHER.read_bytes()


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("sh") is None, reason="needs sh (Git Bash on Windows)")
def test_launcher_runs_the_hook_and_keeps_exit_2(tmp_path):
    """The agent file calls `sh .claude/kit/hook reviewer-bash`: the block must survive the launcher.

    The launcher takes Python from python-path, as the installer records it (the PATH may hold only
    the Windows Store alias)."""
    kit = tmp_path / "my project" / ".claude" / "kit"
    shutil.copytree(LAUNCHER.parent, kit, ignore=shutil.ignore_patterns("__pycache__", "python-path"))
    (kit / "python-path").write_text(sys.executable + "\n", encoding="utf-8")
    stdin = pre_tool_use(tmp_path, "Bash", {"command": "git checkout main"})
    result = subprocess.run(["sh", (kit / "hook").as_posix(), "reviewer-bash"], input=stdin,
                            capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 2, result.stderr
    assert "read-only" in result.stderr


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("sh") is None, reason="needs sh (Git Bash on Windows)")
def test_launcher_fails_closed_without_python(tmp_path):
    kit = tmp_path / ".claude" / "kit"
    kit.mkdir(parents=True)
    shutil.copy(LAUNCHER, kit / "hook")
    (kit / "python-path").write_text(str(tmp_path / "no-such-python") + "\n", encoding="utf-8")
    result = subprocess.run(["sh", (kit / "hook").as_posix(), "reviewer-bash"], input="{}",
                            capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 2
