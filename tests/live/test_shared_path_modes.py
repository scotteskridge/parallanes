"""Plan 13's live check: an append-only shared path in a real lane session (decision 116).

Run with `.venv/Scripts/python -m pytest --live tests/live` (docs/live-checks.md). The installer
runs into a scratch repo with two lanes and the default shared paths, where `docs/changelog.d/**`
is append-only. Lane `api`'s fragment is on main; a session in lane `core` then:
- Writes a new fragment of its own, which must go through (adding is free);
- Edits api's fragment, which the ownership hook must ask about, and with nobody to answer in
  `claude -p`, the edit doesn't happen.
Then a person makes that edit by hand and commits it on the task branch: the installed pre-commit
hook must list it and let the commit through (the owner's yes is the gate, not a refusal later).
"""

import subprocess
import sys
from pathlib import Path

import pytest

from claude_run import git, remove_tree, run_claude, scratch_project

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[2]
FRAGMENTS = "docs/changelog.d"
PROMPT = (
    "Do these in order, each exactly once, and continue even if one is refused: "
    f"1) use the Write tool to create {FRAGMENTS}/core-work.md containing '- core work'; "
    f"2) use the Edit tool to replace 'api work' with 'rewritten' in {FRAGMENTS}/api-work.md."
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
    folder = scratch_project("shared-path-modes")
    for child in folder.iterdir():  # a fresh install every run, in the same (trusted once) folder
        remove_tree(child)
    git(folder, "init", "-q", "-b", "main")
    git(folder, "config", "user.name", "Live Check")
    git(folder, "config", "user.email", "live@example.com")
    subprocess.run(
        [sys.executable, str(ROOT / "kit_setup.py"), "--target", str(folder), "--yes", "--profile", "lanes"], check=True
    )
    config = folder / ".claude" / "kit.toml"
    config.write_text(config.read_text(encoding="utf-8") + LANES, encoding="utf-8")
    (folder / FRAGMENTS).mkdir(parents=True, exist_ok=True)
    (folder / FRAGMENTS / "api-work.md").write_text("- api work\n", encoding="utf-8")
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", "init")
    subprocess.run(["sh", ".claude/kit/parallanes", "lanes", "create"], cwd=folder, check=True)
    lane = folder / ".claude" / "worktrees" / "core"
    git(lane, "switch", "-q", "-c", "core/task")
    return lane


def test_an_append_only_path_takes_new_files_and_asks_before_changing_one():
    lane = lanes_project()
    run = run_claude(
        lane,
        PROMPT,
        permission_mode="bypassPermissions",
        max_turns=10,
        disallowed_tools=["Bash", "PowerShell", "NotebookEdit"],
        expect_hooks=["SessionStart:startup", "PreToolUse:Write", "PreToolUse:Edit"],
    )
    briefing = " ".join(
        e.get("output", "") + e.get("stdout", "")
        for e in run.events
        if e.get("subtype") == "hook_response" and e.get("hook_name") == "SessionStart:startup"
    )
    assert "adding files is free, changing one asks: docs/changelog.d/**" in briefing, briefing
    asks = [
        e
        for e in run.events
        if e.get("subtype") == "hook_response"
        and e.get("hook_name") == "PreToolUse:Edit"
        and "append-only shared path" in e.get("output", "") + e.get("stdout", "")
    ]
    assert asks, [e for e in run.events if e.get("subtype") == "hook_response"]

    assert (lane / FRAGMENTS / "core-work.md").read_text(encoding="utf-8").strip() == "- core work"
    assert (lane / FRAGMENTS / "api-work.md").read_text(encoding="utf-8").strip() == "- api work"
    assert any(path and path.replace("\\", "/").endswith("api-work.md") for path in run.denied_paths())

    # The person's yes, by hand: the installed pre-commit hook lists the change and lets it land.
    (lane / FRAGMENTS / "api-work.md").write_text("- rewritten by a person\n", encoding="utf-8")
    git(lane, "add", "-A")
    done = subprocess.run(["git", "commit", "-q", "-m", "work"], cwd=lane, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "docs/changelog.d/api-work.md:" in done.stderr and "needs a person" in done.stderr, done.stderr
    assert "core-work.md" not in done.stderr
