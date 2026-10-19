"""A hook whose cwd no longer exists (a lane removed while a session was still in it).

PR 56 read the filesystem of the cwd with an unguarded os.stat on macOS/Linux, so the missing
folder raised out of find_root: the protected guard blocked every call and the fail-open hooks
reported an error. Now the root is what the nearest existing folder above the cwd gets, so a nested
kit.toml there can't replace the project's (review round 1). `_CHECK_DEVICE` is forced on so
Windows runs the POSIX path too.
"""

import io
import json
import os
import sys

import pytest

from helpers import make_repo, write
from kitlib import gitdisk, hooks, lanes
from kitlib.config import find_root


@pytest.fixture(params=[True, False], ids=["device-check", "no-device-check"])
def device_check(request, monkeypatch):
    monkeypatch.setattr(gitdisk, "_CHECK_DEVICE", request.param)


@pytest.fixture
def repo(tmp_path):
    repo = make_repo(tmp_path, config=_config())
    write(repo, "a.py", "x = 1\n")
    return repo


def _config() -> str:
    from helpers import RULES_TOML

    return RULES_TOML + '\n[protected]\npaths = ["vendor/**"]\n'


def test_a_missing_folder_is_git_s_to_answer(repo, device_check):
    assert gitdisk.toplevel(repo / "gone" / "deeper") is gitdisk.UNKNOWN


def test_find_root_from_a_missing_folder_walks_to_kit_toml(repo, device_check):
    assert lanes.same_path(find_root(repo / "gone"), repo)


def test_find_root_from_a_missing_folder_outside_any_kit_is_that_folder(tmp_path, device_check):
    gone = tmp_path / "gone"
    assert find_root(gone) == gone.resolve()


def test_a_folder_whose_filesystem_cant_be_read_asks_git(repo, monkeypatch):
    (repo / "sub").mkdir()
    monkeypatch.setattr(gitdisk, "_CHECK_DEVICE", True)
    monkeypatch.setattr(gitdisk, "_device", lambda folder: None if lanes.same_path(folder, repo) else 1)
    assert gitdisk.toplevel(repo / "sub") is gitdisk.UNKNOWN


def test_device_of_a_missing_folder_is_none(tmp_path):
    assert gitdisk._device(tmp_path / "gone") is None


def _run_hook(monkeypatch, name: str, cwd, target, capsys) -> tuple[int, str]:
    payload = {
        "session_id": "test",
        "cwd": str(cwd),
        "hook_event_name": "SessionStart" if name == "lane-router" else "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(target)},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    code = hooks.run(name)
    out = capsys.readouterr()
    return code, out.out + out.err


@pytest.mark.parametrize("name", ["protected", "ownership", "rules-check", "lane-router"])
def test_hooks_run_normally_from_a_missing_cwd(repo, device_check, monkeypatch, capsys, name):
    code, output = _run_hook(monkeypatch, name, repo / "gone", repo / "a.py", capsys)
    assert (code, output) == (0, "")


def test_the_protected_guard_still_blocks_a_protected_path_from_a_missing_cwd(repo, device_check, monkeypatch, capsys):
    code, output = _run_hook(monkeypatch, "protected", repo / "gone", repo / "vendor" / "lib.py", capsys)
    assert code == 2
    assert "Blocked by the kit's protected-paths guard" in output


# ---- review round 1 --------------------------------------------------------------------------------


def test_a_nested_kit_toml_above_a_missing_cwd_cant_take_the_guard(repo, device_check, monkeypatch, capsys):
    # The nearest kit.toml above a missing cwd is a nested one with no [protected]: the project's
    # own config must still decide, as it does for an existing cwd there.
    write(repo, "sub/.claude/kit.toml", (repo / ".claude" / "kit.toml").read_text().split("[protected]")[0])
    assert lanes.same_path(find_root(repo / "sub" / "gone"), find_root(repo / "sub"))
    assert lanes.same_path(find_root(repo / "sub" / "gone"), repo)
    code, output = _run_hook(monkeypatch, "protected", repo / "sub" / "gone", repo / "vendor" / "lib.py", capsys)
    assert code == 2
    assert "Blocked by the kit's protected-paths guard" in output


def test_a_start_whose_filesystem_cant_be_read_asks_git(repo, monkeypatch):
    # Without the start's device the walk can't see a mount point, so it mustn't answer.
    (repo / "sub").mkdir()
    monkeypatch.setattr(gitdisk, "_CHECK_DEVICE", True)
    monkeypatch.setattr(gitdisk, "_device", lambda folder: None)
    assert gitdisk.toplevel(repo / "sub") is gitdisk.UNKNOWN


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="POSIX permissions, not as root")
@pytest.mark.parametrize("below", ["inner", ""], ids=["below-it", "the-folder-itself"])
def test_a_cwd_in_an_unsearchable_folder_still_finds_the_root(repo, monkeypatch, capsys, below):
    locked = repo / "locked"
    (locked / "inner").mkdir(parents=True)
    cwd = locked / below if below else locked
    locked.chmod(0)
    try:
        assert lanes.same_path(find_root(cwd), repo)
        code, output = _run_hook(monkeypatch, "protected", cwd, repo / "vendor" / "lib.py", capsys)
    finally:
        locked.chmod(0o755)
    assert code == 2
    assert "Blocked by the kit's protected-paths guard" in output
