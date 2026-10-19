"""Plan 14's live check: Claude Code's session lock on a lane (decision 119).

Run with `.venv/Scripts/python -m pytest --live tests/live` (docs/live-checks.md). The installer
runs into a scratch repo with a lane `core`; `claude -p --worktree core` from the main checkout then
opens that lane. The lane-router must warn in the briefing that this session holds Claude Code's
lock. The `-p` run leaves the lock behind: `lanes status` must name it as not running, and
`lanes remove core` must clear it and remove the lane, where git alone refuses.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from claude_run import git, remove_tree, run_claude, scratch_project

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[2]
LANES = """
[[lanes]]
name = "core"
owns = ["src/core/**"]
"""


def lanes_project() -> Path:
    folder = scratch_project("session-lock")
    for child in folder.iterdir():  # a fresh install every run, in the same folder
        remove_tree(child)
    git(folder, "init", "-q", "-b", "main")
    git(folder, "config", "user.name", "Live Check")
    git(folder, "config", "user.email", "live@example.com")
    subprocess.run([sys.executable, str(ROOT / "kit_setup.py"), "--target", str(folder), "--yes"], check=True)
    config = folder / ".claude" / "kit.toml"
    config.write_text(config.read_text(encoding="utf-8") + LANES, encoding="utf-8")
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", "init")
    subprocess.run(["sh", ".claude/kit/parallanes", "lanes", "create"], cwd=folder, check=True)
    return folder


def kit(folder: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["sh", ".claude/kit/parallanes", *args], cwd=folder, capture_output=True, text=True)


def test_a_worktree_session_is_warned_and_its_leftover_lock_is_cleared():
    project = lanes_project()
    lane = project / ".claude" / "worktrees" / "core"
    run = run_claude(
        project,
        "Reply with the single word ok.",
        permission_mode="default",
        max_turns=2,
        extra_args=["--worktree", "core"],
        expect_hooks=["SessionStart:startup"],
    )
    briefing = " ".join(
        e.get("output", "") + e.get("stdout", "")
        for e in run.events
        if e.get("subtype") == "hook_response" and e.get("hook_name") == "SessionStart:startup"
    )
    assert "Lane: core" in briefing, briefing  # the session really opened the lane
    assert "holds this lane's `claude --worktree core` lock" in briefing, briefing
    assert "tell the user now" in briefing

    porcelain = git(project, "worktree", "list", "--porcelain")
    assert "locked claude session core (pid " in porcelain, porcelain  # the -p run left it

    status = kit(project, "lanes", "status")
    assert status.returncode == 0, status.stderr
    assert "Claude Code session lock (pid " in status.stdout and "not running" in status.stdout, status.stdout

    removed = kit(project, "lanes", "remove", "core")
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert "cleared a leftover Claude Code session lock" in removed.stdout, removed.stdout
    assert not lane.exists()
