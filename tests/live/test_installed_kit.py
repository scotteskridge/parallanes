"""Plan 08's live check: a project set up by the installer has its hooks and deny rules working.

Run with `.venv/Scripts/python -m pytest --live tests/live` (docs/live-checks.md). The installer runs
into a scratch repo, `vendor/**` is made protected, and one session tries three things:
- an ordinary Edit, which must go through: the fail-open hooks (ownership, rules-check) fire and
  don't get in the way;
- `cp` into `vendor/`, which deny rules don't cover: the protected hook's own block, seen in its
  `hook_response` (exit 2 and its message), shows the installed wiring reached it;
- a Write into `vendor/`, which the deny rule that `settings sync` wrote must refuse.
The SessionStart hook (lane-router) must fire too. What these hooks do inside a lane was checked
live in plan 04; this check is about the installer's wiring.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from claude_run import run_claude, scratch_project

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[2]

PROMPT = (
    "Do these in order, each exactly once, and continue even if one is refused: "
    "1) use the Edit tool to replace 'original' with 'changed' in notes.txt; "
    "2) run this Bash command: cp notes.txt vendor/copied.txt ; "
    "3) use the Write tool to create vendor/written.txt containing 'x'."
)


def installed_project():
    folder = scratch_project("installed-kit")
    for child in folder.iterdir():  # a fresh install every run, in the same (trusted once) folder
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=folder, check=True)
    subprocess.run([sys.executable, str(ROOT / "kit_setup.py"), "--target", str(folder), "--yes"], check=True)
    config = folder / ".claude" / "kit.toml"
    text = config.read_text(encoding="utf-8")
    assert "paths = []" in text
    config.write_text(text.replace("paths = []", 'paths = ["vendor/**"]', 1), encoding="utf-8")
    subprocess.run(["sh", ".claude/kit/worklanes", "settings", "sync"], cwd=folder, check=True)
    (folder / "vendor").mkdir()
    (folder / "notes.txt").write_text("original\n", encoding="utf-8")
    return folder


def test_installed_hooks_and_deny_rules_work():
    folder = installed_project()
    run = run_claude(
        folder,
        PROMPT,
        permission_mode="bypassPermissions",
        max_turns=10,
        disallowed_tools=["PowerShell"],
        expect_hooks=["SessionStart:startup", "PreToolUse:Edit", "PostToolUse:Edit", "PreToolUse:Bash"],
    )
    started = [e.get("hook_name") for e in run.events if e.get("subtype") == "hook_started"]
    assert started.count("PreToolUse:Edit") >= 2, started  # protected and ownership both wired on Edit
    blocks = [
        e
        for e in run.events
        if e.get("subtype") == "hook_response" and e.get("hook_name") == "PreToolUse:Bash" and e.get("exit_code") == 2
    ]
    assert any("protected-paths guard" in e.get("stderr", "") for e in blocks), blocks

    assert (folder / "notes.txt").read_text(encoding="utf-8").strip() == "changed", run.result.get("result")
    assert not (folder / "vendor" / "copied.txt").exists()
    assert not (folder / "vendor" / "written.txt").exists()
    assert any(path and path.replace("\\", "/").endswith("vendor/written.txt") for path in run.denied_paths())
