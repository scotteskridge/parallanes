"""The protected-paths PreToolUse hook: blocks with exit 2, and fails closed (decisions 27, 30, 33, 34).

In PreToolUse only exit 2 blocks; exit 1 and timeouts let the call through. So every error path
must exit 2, and no test here may accept any other non-zero code.
"""
import json
import os

import pytest

from helpers import RULES_TOML, git, make_repo, run_cli, write

PROTECTED_TOML = RULES_TOML + """
[protected]
paths = ["vendor/**"]
"""


def pre_tool_use(cwd, tool, tool_input, mode="default"):
    return json.dumps(
        {
            "session_id": "test",
            "cwd": str(cwd),
            "hook_event_name": "PreToolUse",
            "permission_mode": mode,
            "tool_name": tool,
            "tool_input": tool_input,
        }
    )


def hook(cwd, payload):
    return run_cli(cwd, "hook", "protected", stdin=payload)


def bash(repo, command, mode="default", tool="Bash"):
    return hook(repo, pre_tool_use(repo, tool, {"command": command}, mode))


def edit(repo, rel, tool="Edit", mode="default"):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    return hook(repo, pre_tool_use(repo, tool, {key: str(repo / rel)}, mode))


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path, config=PROTECTED_TOML)


def assert_blocked(result, *words):
    assert result.returncode == 2, (result.returncode, result.stderr)
    assert "Traceback" not in result.stderr
    for word in words:
        assert word in result.stderr, result.stderr


def assert_allowed(result):
    assert (result.returncode, result.stderr) == (0, ""), result.stderr


def test_protected_command_is_blocked_with_the_reason(repo):
    assert_blocked(bash(repo, "git -C . push origin main --force"), "git push --force", "kit.toml", "ask the user")


def test_powershell_command_is_blocked(repo):
    assert_blocked(bash(repo, "GIT reset --hard", tool="PowerShell"), "git reset --hard")


def test_clean_command_is_allowed(repo):
    assert_allowed(bash(repo, "git status && python -m pytest -q"))


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit", "NotebookEdit"])
def test_edit_of_a_protected_path_is_blocked(repo, tool):
    assert_blocked(edit(repo, "vendor/lib.py", tool=tool), "vendor/lib.py", "vendor/**")


def test_edit_of_a_secret_is_blocked(repo):
    assert_blocked(edit(repo, "config/.env"), ".env")


def test_edit_elsewhere_is_allowed(repo):
    assert_allowed(edit(repo, "src/app.py"))
    assert_allowed(edit(repo, ".env.example"))


def test_edit_outside_the_project_is_allowed(repo, tmp_path):
    payload = pre_tool_use(repo, "Write", {"file_path": str(tmp_path / "elsewhere" / "vendor" / "x")})
    assert_allowed(hook(repo, payload))


@pytest.mark.parametrize(
    "command, tool",
    [
        ("Set-Content -Path vendor\\lib.py -Value x", "PowerShell"),
        ("Remove-Item vendor -Recurse -Force", "PowerShell"),
        ("'x' | Out-File .\\vendor\\lib.py", "PowerShell"),
        ("rm -rf vendor", "Bash"),
        ("echo x > vendor/lib.py", "Bash"),
        ("mv vendor/lib.py src/", "Bash"),
    ],
)
def test_shell_writes_to_protected_paths_are_blocked(repo, command, tool):
    assert_blocked(bash(repo, command, tool=tool), "vendor")


def test_shell_write_from_a_subfolder_resolves_against_cwd(repo):
    (repo / "src").mkdir()
    payload = pre_tool_use(repo / "src", "Bash", {"command": "rm ../vendor/lib.py"})
    assert_blocked(hook(repo / "src", payload), "vendor/lib.py")
    payload = pre_tool_use(repo / "src", "Bash", {"command": "rm vendor/lib.py"})  # src/vendor/lib.py
    assert_allowed(hook(repo / "src", payload))


@pytest.mark.parametrize("rel", [".claude/kit.toml", ".claude/settings.json", ".githooks/pre-commit"])
def test_kit_config_edits_blocked_only_in_bypass_mode(repo, rel):
    assert_allowed(edit(repo, rel))
    assert_allowed(edit(repo, rel, mode="acceptEdits"))
    assert_blocked(edit(repo, rel, mode="bypassPermissions"), "bypassPermissions")


def test_kit_config_guard_can_be_switched_off(tmp_path):
    repo = make_repo(tmp_path, config=PROTECTED_TOML + "guard_kit = false\n")
    assert_allowed(edit(repo, ".claude/kit.toml", mode="bypassPermissions"))


@pytest.mark.parametrize(
    "command",
    ["KIT_ALLOW_PROTECTED=1 git commit -m x", "git config core.hooksPath /dev/null", "git commit --no-verify -m x"],
)
def test_the_agent_cannot_switch_the_local_checks_off(repo, command):
    assert_blocked(bash(repo, command))


def test_each_lane_uses_its_own_worktree_config(repo):
    # The root comes from the call's cwd: a worktree with a different kit.toml gets its own rules.
    write(repo, "README.md", "x\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    lane = repo.parent / "lane one"
    git(repo, "worktree", "add", "-q", str(lane), "-b", "lane/one")
    write(lane, ".claude/kit.toml", RULES_TOML + '\n[protected]\npaths = ["assets/**"]\n')
    assert_blocked(edit(lane, "assets/a.png"), "assets/**")
    assert_allowed(edit(lane, "vendor/lib.py"))
    assert_blocked(edit(repo, "vendor/lib.py"))


def test_no_kit_toml_allows_everything(tmp_path):
    repo = make_repo(tmp_path, config=None)
    assert_allowed(bash(repo, "git push --force"))


def test_broken_config_blocks_with_what_to_fix(tmp_path):
    repo = make_repo(tmp_path, config=PROTECTED_TOML + "pathes = []\n")
    assert_blocked(bash(repo, "git status"), "pathes", "kit.toml")


@pytest.mark.parametrize("stdin", ["", "not json", "[]", '"text"'])
def test_bad_input_blocks(repo, stdin):
    assert_blocked(hook(repo, stdin), "Blocked")


def test_shell_call_without_a_command_blocks(repo):
    assert_blocked(hook(repo, pre_tool_use(repo, "Bash", {})), "Blocked")


def test_an_internal_crash_blocks_without_a_traceback(repo):
    # Simulate a bug inside the kit: a kitlib module that raises on import of the check.
    env_file = repo / "sitecustomize.py"
    env_file.write_text(
        "import kitlib.protected as p\n"
        "def boom(*a, **k):\n    raise RuntimeError('simulated bug')\n"
        "p.check_tool_call = boom\n",
        encoding="utf-8",
    )
    import subprocess
    import sys

    from helpers import CLI

    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(CLI.parent), str(repo)]))
    result = subprocess.run(
        [sys.executable, str(CLI), "hook", "protected"],
        cwd=repo, input=pre_tool_use(repo, "Bash", {"command": "ls"}),
        capture_output=True, text=True, encoding="utf-8", env=env,
    )
    assert_blocked(result, "simulated bug", "Tell the user")


def test_other_tools_are_ignored(repo):
    assert_allowed(hook(repo, pre_tool_use(repo, "Read", {"file_path": str(repo / "vendor" / "x")})))
    assert_allowed(hook(repo, pre_tool_use(repo, "WebFetch", {"url": "https://example.com"})))


def test_a_typo_in_the_hook_name_blocks_in_pre_tool_use(repo):
    # A mistyped settings.json entry must not switch the guard off: PreToolUse fails closed.
    result = run_cli(repo, "hook", "protectd", stdin=pre_tool_use(repo, "Bash", {"command": "ls"}))
    assert_blocked(result, "protectd")


def test_a_typo_in_the_hook_name_stays_non_blocking_after_an_edit(repo):
    # PostToolUse (rules-check) keeps failing open: exit 2 there would nag Claude after every edit.
    payload = json.dumps({"hook_event_name": "PostToolUse", "cwd": str(repo), "tool_name": "Edit", "tool_input": {}})
    assert run_cli(repo, "hook", "rules-chek", stdin=payload).returncode == 1
