"""The ownership PreToolUse hook: out-of-lane edits ask the user; it fails open (decision 41)."""

import json
import os

import pytest

from helpers import run_cli, write
from lane_helpers import LANES_TOML, lane_dir, lanes_repo

pytestmark = pytest.mark.slow  # real repos, worktrees and CLI processes: seconds a test on Windows

SHARED_TOML = LANES_TOML.replace(
    'integration_branch = "main"', 'integration_branch = "main"\nshared_paths = ["docs/plans/**"]'
)


def pre_tool_use(cwd, target, tool="Edit", mode="default"):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    return json.dumps(
        {
            "session_id": "t",
            "cwd": str(cwd),
            "hook_event_name": "PreToolUse",
            "permission_mode": mode,
            "tool_name": tool,
            "tool_input": {key: str(target)},
        }
    )


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
    assert_asks(
        hook(lane, lane / "src/api/routes.py", tool), "src/api/routes.py", "'core'", "src/core/**", "docs/plans/**"
    )


def test_a_file_a_more_specific_lane_owns_asks_the_wider_lane(tmp_path):
    # Decision 97: api's src/** also matches src/core/, but core's src/core/** is more specific.
    repo = lanes_repo(tmp_path, config=LANES_TOML.replace('owns = ["src/api/**"]', 'owns = ["src/**"]'))
    assert run_cli(repo, "lanes", "create").returncode == 0
    api = lane_dir(repo, "api")
    reason = json.loads(hook(api, api / "src/core/a.py").stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    # Review round 1: one plain sentence for why, not parentheses nested in "outside the lane".
    assert reason.startswith(
        "src/core/a.py isn't lane 'api''s to change: src/** matches it, but lane 'core' owns it: "
        "src/core/** is more specific. Lane 'api' owns src/**"
    ), reason
    assert_allowed(hook(api, api / "src/api/x.py"))
    assert_allowed(hook(lane_dir(repo, "core"), lane_dir(repo, "core") / "src/core/a.py"))


def test_a_file_no_lane_owns_asks_with_the_exact_kit_toml_line(lane):
    # Backlog ownership-fix-hint: the trial's .gitignore (F8, F11) stopped with no way through.
    assert_asks(
        hook(lane, lane / ".gitignore"),
        "no lane owns it",
        "Add \"/.gitignore\" to lane 'core''s owns in .claude/kit.toml.",
        "branch that isn't a lane's",
        "lanes sync",
        # Review round 1: approving the edit was what failed in the trial; say the commit still won't pass.
        "Approving this edit isn't enough",
    )
    assert (
        "Allow only if"
        not in json.loads(hook(lane, lane / ".gitignore").stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_editing_the_lane_policy_asks_without_offering_it_to_the_lane(lane):
    # Review round 1 (both reviewers): a lane owning kit.toml could widen itself.
    reason = json.loads(hook(lane, lane / ".claude/kit.toml").stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "the lane policy belongs to no lane" in reason and "Add " not in reason


def test_a_file_another_lane_owns_asks_without_offering_to_widen(lane):
    reason = json.loads(hook(lane, lane / "src/api/routes.py").stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "owned by lane 'api'" in reason and "Make this change from that lane instead." in reason
    assert "Add " not in reason and "lanes sync" not in reason


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
    repo = lanes_repo(
        tmp_path,
        config=LANES_TOML.replace('integration_branch = "main"', 'integration_branch = "main"\nownership = "off"'),
    )
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


# ---- from the first review ---------------------------------------------------------------------


def test_editing_the_main_checkout_or_another_lane_asks(lane):
    main = lane.parents[2]
    assert_asks(hook(lane, main / "src/core/x.py"), "main checkout")
    assert_asks(hook(lane, main / ".claude/worktrees/api/src/core/x.py"), "lane 'api'")


@pytest.mark.skipif(os.name != "nt", reason="Windows paths are case-insensitive")
def test_owned_path_in_another_case_is_allowed(lane):
    assert_allowed(hook(lane, lane / "SRC/Core/x.py"))


@pytest.mark.parametrize(
    "name, event", [("ownership", "PreToolUse"), ("lane-router", "SessionStart"), ("rules-check", "PreToolUse")]
)
def test_kit_that_cannot_import_fails_open_for_the_lane_hooks(tmp_path, name, event):
    # Only the protected guard fails closed on an old Python (decisions 9, 33, 40, 41).
    import subprocess
    import sys

    from helpers import CLI

    fake = tmp_path / "fakes"
    fake.mkdir()
    (fake / "tomllib.py").write_text("raise ImportError('simulated: no tomllib')\n", encoding="utf-8")
    payload = json.dumps(
        {
            "cwd": str(tmp_path),
            "hook_event_name": event,
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "a.py")},
        }
    )
    result = subprocess.run(
        [sys.executable, str(CLI), "hook", name],
        cwd=tmp_path,
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=dict(os.environ, PYTHONPATH=str(fake)),
    )
    assert result.returncode == 1, result
    assert "simulated: no tomllib" in result.stderr
