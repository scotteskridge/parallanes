"""The ownership PreToolUse hook: out-of-lane edits ask the user; it fails open (decision 41)."""
import json
import os

import pytest

from helpers import run_cli, write
from lane_helpers import LANES_TOML, lane_dir, lanes_repo

SHARED_TOML = LANES_TOML.replace(
    'integration_branch = "main"', 'integration_branch = "main"\nshared_paths = ["docs/plans/**"]'
)


def pre_tool_use(cwd, target, tool="Edit", mode="default"):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    return json.dumps({
        "session_id": "t", "cwd": str(cwd), "hook_event_name": "PreToolUse", "permission_mode": mode,
        "tool_name": tool, "tool_input": {key: str(target)},
    })


def hook(cwd, target, tool="Edit"):
    return run_cli(cwd, "hook", "ownership", stdin=pre_tool_use(cwd, target, tool))


def assert_allowed(result):
    assert (result.returncode, result.stdout, result.stderr) == (0, "", ""), result


def assert_asks(result, *words):
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "ask"
    for word in words:
        assert word in output["permissionDecisionReason"], output


@pytest.fixture
def lane(tmp_path):
    repo = lanes_repo(tmp_path, config=SHARED_TOML)
    assert run_cli(repo, "lanes", "create").returncode == 0
    return lane_dir(repo, "core")


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit", "NotebookEdit"])
def test_owned_path_is_allowed(lane, tool):
    assert_allowed(hook(lane, lane / "src/core/new.py", tool))


def test_shared_path_is_allowed(lane):
    assert_allowed(hook(lane, lane / "docs/plans/2026-10-04-x.md"))


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit", "NotebookEdit"])
def test_out_of_lane_path_asks_with_the_reason(lane, tool):
    assert_asks(hook(lane, lane / "src/api/routes.py", tool), "src/api/routes.py", "'core'", "src/core/**", "docs/plans/**")


def test_relative_path_from_a_subfolder(lane):
    sub = lane / "src"
    assert_asks(run_cli(sub, "hook", "ownership", stdin=pre_tool_use(sub, "api/x.py")), "src/api/x.py")
    assert_allowed(run_cli(sub, "hook", "ownership", stdin=pre_tool_use(sub, "core/x.py")))


@pytest.mark.skipif(os.name != "nt", reason="backslash is a separator only on Windows")
def test_windows_separators(lane):
    assert_asks(hook(lane, str(lane) + "\\src\\api\\x.py"))
    assert_allowed(hook(lane, str(lane) + "\\src\\core\\x.py"))


@pytest.mark.skipif(os.name != "nt", reason="Windows paths are case-insensitive")
def test_case_of_the_lane_folder_does_not_matter(lane):
    assert_asks(hook(lane, str(lane / "src/api/x.py").upper()))


def test_outside_the_project_is_allowed(lane, tmp_path):
    assert_allowed(hook(lane, tmp_path / "elsewhere.txt"))


def test_main_checkout_is_not_judged(lane):
    main = lane.parents[2]
    assert_allowed(hook(main, main / "src/api/x.py"))


def test_ownership_off(tmp_path):
    repo = lanes_repo(tmp_path, config=LANES_TOML.replace(
        'integration_branch = "main"', 'integration_branch = "main"\nownership = "off"'))
    assert run_cli(repo, "lanes", "create", "core").returncode == 0
    lane = lane_dir(repo, "core")
    assert_allowed(hook(lane, lane / "src/api/x.py"))


def test_no_kit_is_allowed(tmp_path):
    folder = tmp_path / "plain"
    folder.mkdir()
    assert_allowed(hook(folder, folder / "a.py"))


def test_tool_without_a_path_is_allowed(lane):
    payload = json.dumps({"cwd": str(lane), "hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": {}})
    assert_allowed(run_cli(lane, "hook", "ownership", stdin=payload))


@pytest.mark.parametrize("stdin", ["not json", "[]"])
def test_bad_input_fails_open(lane, stdin):
    result = run_cli(lane, "hook", "ownership", stdin=stdin)
    assert result.returncode == 1
    assert result.stdout == "" and "Traceback" not in result.stderr


def test_broken_config_fails_open(lane):
    write(lane, ".claude/kit.toml", "[project\n")
    result = hook(lane, lane / "src/api/x.py")
    assert result.returncode == 1
    assert "kit.toml" in result.stderr and "Traceback" not in result.stderr
