"""Plan 15's live check: the faster hooks still guard a real lane session (decision 120).

Run with `.venv/Scripts/python -m pytest --live tests/live` (docs/live-checks.md). Plan 15 changed
how every per-call hook finds the project root and the lane (from git's files on disk, not git), what
each hook imports, and the `hook` launcher. The installer runs into a scratch repo with two lanes
and `vendor/**` protected; a session in lane `core` then:
- Edits its own file, which must go through: protected, ownership and rules-check all fire and pass;
- Copies into `vendor/` with Bash, which the protected hook must block (exit 2, its message): the
  root it found from the lane's `.git` file is right;
- Writes lane `api`'s file, which the ownership hook must ask about: the lane it found from disk
  is right. With nobody to answer in `claude -p`, the write doesn't happen.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from claude_run import git, remove_tree, run_claude, scratch_project

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[2]
PROMPT = (
    "Do these in order, each exactly once, and continue even if one is refused: "
    "1) use the Edit tool to replace 'x = 1' with 'x = 2' in src/core/a.py; "
    "2) run this Bash command: cp src/core/a.py vendor/copied.py ; "
    "3) use the Write tool to create src/api/b.py containing 'y = 1'."
)
LANES = """
[[lanes]]
name = "core"
owns = ["src/core/**"]

[[lanes]]
name = "api"
owns = ["src/api/**"]
"""


def lanes_project():
    folder = scratch_project("hook-latency")
    for child in folder.iterdir():  # a fresh install every run, in the same (trusted once) folder
        remove_tree(child)
    git(folder, "init", "-q", "-b", "main")
    git(folder, "config", "user.name", "Live Check")
    git(folder, "config", "user.email", "live@example.com")
    subprocess.run(
        [sys.executable, str(ROOT / "kit_setup.py"), "--target", str(folder), "--yes", "--profile", "lanes"], check=True
    )
    config = folder / ".claude" / "kit.toml"
    text = config.read_text(encoding="utf-8")
    assert "paths = []" in text
    config.write_text(text.replace("paths = []", 'paths = ["vendor/**"]', 1) + LANES, encoding="utf-8")
    subprocess.run(["sh", ".claude/kit/parallanes", "settings", "sync"], cwd=folder, check=True)
    (folder / "src" / "core").mkdir(parents=True)
    (folder / "src" / "core" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (folder / "vendor").mkdir()
    (folder / "vendor" / "README.md").write_text("third-party code\n", encoding="utf-8")
    git(folder, "add", "-A")
    # A person's commit: the installed pre-commit check refuses vendor/ without the override.
    env = dict(os.environ, KIT_ALLOW_PROTECTED="1")
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=folder, env=env, check=True)
    subprocess.run(["sh", ".claude/kit/parallanes", "lanes", "create"], cwd=folder, check=True)
    lane = folder / ".claude" / "worktrees" / "core"
    git(lane, "switch", "-q", "-c", "core/task")
    return lane


def responses(run, hook_name):
    return [e for e in run.events if e.get("subtype") == "hook_response" and e.get("hook_name") == hook_name]


def test_the_faster_hooks_still_block_and_ask_in_a_lane():
    lane = lanes_project()
    run = run_claude(
        lane,
        PROMPT,
        permission_mode="bypassPermissions",
        max_turns=10,
        disallowed_tools=["PowerShell", "NotebookEdit"],
        expect_hooks=["SessionStart:startup", "PreToolUse:Edit", "PostToolUse:Edit", "PreToolUse:Bash"],
    )
    started = [e.get("hook_name") for e in run.events if e.get("subtype") == "hook_started"]
    assert started.count("PreToolUse:Edit") >= 2, started  # protected and ownership

    briefing = " ".join(e.get("output", "") + e.get("stdout", "") for e in responses(run, "SessionStart:startup"))
    assert "Lane: core" in briefing, briefing

    blocks = [e for e in responses(run, "PreToolUse:Bash") if e.get("exit_code") == 2]
    assert any("protected-paths guard" in e.get("stderr", "") for e in blocks), responses(run, "PreToolUse:Bash")

    asks = [
        e
        for e in responses(run, "PreToolUse:Write")
        if "isn't lane 'core'" in e.get("output", "") + e.get("stdout", "")
    ]
    assert asks, responses(run, "PreToolUse:Write")

    assert (lane / "src" / "core" / "a.py").read_text(encoding="utf-8").strip() == "x = 2", run.result.get("result")
    assert not (lane / "vendor" / "copied.py").exists()
    assert not (lane / "src" / "api" / "b.py").exists()
    # No hook failed on the way: every kit hook either passed (0) or answered on purpose (2).
    failed = [e for e in run.events if e.get("subtype") == "hook_response" and e.get("exit_code") not in (0, 2)]
    assert not failed, failed
