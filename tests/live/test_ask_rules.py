"""Decision 92's live check, repeatable: ask rules are never auto-approved, even in bypass mode.

Run with `python -m pytest --live tests/live` (docs/live-checks.md). One file has an ask rule, one
a deny rule and one neither. The deny rule shows the project settings loaded; a PreToolUse hook on
Edit shows hooks loaded (`--bare` would skip it); the control run without the ask rule shows the
ask rule is what stops the edit.
"""

import json

import pytest

from claude_run import run_claude, scratch_project

pytestmark = pytest.mark.live

PROMPT = (
    "Read free.txt, guarded.txt and denied.txt, then use the Edit tool to replace 'original' with "
    "'changed' in each, one Edit call per file. Do not use any other way to change them."
)
EDIT_HOOK = {"PreToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "exit 0"}]}]}


def project(name: str, ask: bool):
    folder = scratch_project(f"ask-rules-{name}")  # one folder per test: xdist runs them at once
    (folder / ".claude").mkdir(exist_ok=True)
    permissions = {"deny": ["Edit(/denied.txt)"], **({"ask": ["Edit(/guarded.txt)"]} if ask else {})}
    (folder / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": permissions, "hooks": EDIT_HOOK}), encoding="utf-8"
    )
    for file in ("free", "guarded", "denied"):
        (folder / f"{file}.txt").write_text("original\n", encoding="utf-8")
    return folder


def edit_all(folder, mode):
    return run_claude(
        folder,
        PROMPT,
        permission_mode=mode,
        max_turns=10,
        disallowed_tools=["Bash", "PowerShell", "Write", "NotebookEdit"],
        expect_hooks=["PreToolUse:Edit"],
    )


def changed(folder, name):
    return (folder / f"{name}.txt").read_text(encoding="utf-8").strip() == "changed"


@pytest.mark.parametrize("mode", ["bypassPermissions", "acceptEdits"])
def test_an_ask_rule_stops_the_edit_in_modes_that_skip_prompts(mode):
    folder = project(mode, ask=True)
    run = edit_all(folder, mode)
    assert changed(folder, "free"), run.result.get("result")
    assert not changed(folder, "denied")  # the project settings loaded
    assert not changed(folder, "guarded")
    assert any(path and path.endswith("guarded.txt") for path in run.denied_paths()), run.denied_paths()


def test_without_the_ask_rule_the_same_edit_goes_through():
    folder = project("control", ask=False)
    edit_all(folder, "bypassPermissions")
    assert changed(folder, "guarded") and changed(folder, "free")
    assert not changed(folder, "denied")
