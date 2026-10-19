"""The project root and a lane's main checkout, read from disk without git (plan 15, decision 120).

Every hook call used to start with `git rev-parse` (~70 ms on Windows), and the ownership hook ran
three more to find the lane. On the normal layout the answers come from `.git` and git's documented
`gitdir:` / `commondir` files; any other layout falls back to git, so it is slower, never wrong.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from helpers import git, make_repo, run_cli, write
from kitlib import config as config_module
from kitlib import lanes
from kitlib.config import find_root, load
from lane_helpers import lane_dir, lanes_repo

pytestmark = pytest.mark.slow  # real repos and worktrees


def git_toplevel(folder: Path) -> Path:
    return Path(git(folder, "rev-parse", "--show-toplevel").strip())


def same(a: Path, b: Path) -> bool:
    return lanes.same_path(a, b)


@pytest.fixture
def no_git(monkeypatch):
    """Fails the test if anything starts a process: the disk path must not need git."""

    monkeypatch.setattr(subprocess, "run", _refuse)
    monkeypatch.setattr(subprocess, "Popen", _refuse)


@pytest.fixture
def lane(tmp_path):
    repo = lanes_repo(tmp_path, origin=False)
    assert run_cli(repo, "lanes", "create").returncode == 0
    return lane_dir(repo, "core")


def test_disk_root_matches_git_in_the_main_checkout_lane_and_subfolders(lane):
    main = lane.parents[2]
    (lane / "src" / "core" / "deep dir").mkdir(parents=True)
    (main / "src" / "core" / "deep dir").mkdir(parents=True)
    folders = [main, main / "src" / "core" / "deep dir", lane, lane / "src" / "core" / "deep dir"]
    expected = [git_toplevel(folder) for folder in folders]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subprocess, "run", _refuse)
        found = [find_root(folder) for folder in folders]
    for folder, want, got in zip(folders, expected, found, strict=True):
        assert same(got, want), (folder, got, want)


def test_disk_locate_matches_git_for_main_checkout_and_lane(lane, no_git):
    main = lane.parents[2]
    assert [same(p, main) for p in lanes.locate(main)] == [True, True]
    top, found_main = lanes.locate(lane / "src")
    assert same(top, lane) and same(found_main, main)
    assert lanes.current_lane(lane, load(lane)).name == "core"


def test_ownership_decision_needs_no_git_in_a_lane(lane, no_git):
    from kitlib import lane_hooks

    payload = {"cwd": str(lane), "tool_input": {"file_path": str(lane / "src" / "api" / "x.py")}}
    assert "isn't lane 'core'" in lane_hooks.ownership_reason(payload)
    payload["tool_input"]["file_path"] = str(lane / "src" / "core" / "x.py")
    assert lane_hooks.ownership_reason(payload) is None


def test_root_outside_git_is_the_folder_with_kit_toml(tmp_path, no_git):
    project = tmp_path / "no git here"
    write(project, ".claude/kit.toml", "")
    (project / "sub").mkdir()
    assert same(find_root(project / "sub"), project)


def test_an_empty_dot_git_folder_is_not_a_repository(tmp_path):
    # git skips a `.git` that isn't a repository and keeps looking up; so must the disk walk.
    repo = make_repo(tmp_path)
    (repo / "sub" / ".git").mkdir(parents=True)
    assert same(find_root(repo / "sub"), git_toplevel(repo / "sub"))


@pytest.mark.parametrize("variable", ["GIT_DIR", "GIT_WORK_TREE", "GIT_CEILING_DIRECTORIES"])
def test_git_environment_variables_send_the_question_to_git(tmp_path, monkeypatch, variable):
    repo = make_repo(tmp_path)
    other = make_repo(tmp_path, name="other project")
    values = {
        "GIT_DIR": str(other / ".git"),
        "GIT_WORK_TREE": str(other),
        "GIT_CEILING_DIRECTORIES": str(tmp_path),
    }
    if variable == "GIT_WORK_TREE":
        monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv(variable, values[variable])
    calls = []
    real = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a[0]) or real(*a, **k))
    find_root(repo)
    assert calls and calls[0][:2] == ["git", "rev-parse"]


def test_core_worktree_in_the_repository_config_sends_the_question_to_git(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "elsewhere").mkdir()
    git(repo, "config", "core.worktree", str(repo / "elsewhere"))
    assert same(find_root(repo), git_toplevel(repo))


def test_garbled_dot_git_file_falls_back(lane):
    # Rewritten in place: Git for Windows marks it hidden, and Windows refuses to recreate a hidden file.
    with open(lane / ".git", "r+", encoding="utf-8") as handle:
        handle.truncate(0)
        handle.write("not a gitdir line\n")
    # git can't use it either: no top level; outside git, the folder holding kit.toml is the root.
    assert same(find_root(lane / "src"), lane)
    assert lanes.locate(lane) == (None, None)


def test_separate_git_dir_main_checkout_matches_git(tmp_path):
    # Its main checkout is read from disk (no commondir: the git dir is the common one); its lanes
    # go to git, which test_lanes.py covers.
    repo = lanes_repo(tmp_path, origin=False)
    git(repo, "init", "-q", f"--separate-git-dir={tmp_path / 'git store'}")
    assert same(find_root(repo / "src"), repo)
    top, main = lanes.locate(repo)
    assert same(top, repo) and same(main, repo)


def test_find_root_loads_no_subprocess_module_on_the_normal_layout(tmp_path):
    # Checked in a fresh Python: importing subprocess alone is ~15 ms of every hook call.
    repo = make_repo(tmp_path)
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); from kitlib.config import find_root; "
        "from pathlib import Path; find_root(Path(sys.argv[2])); print('subprocess' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(Path(config_module.__file__).parent.parent), str(repo)],
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "False", result


def _refuse(*args, **kwargs):
    raise AssertionError(f"started a process: {args[0] if args else kwargs.get('args')}")


# ---- review round 1: layouts git answers differently -------------------------------------------------


def test_a_dot_git_holding_only_head_is_not_a_repository(tmp_path):
    # git also needs objects/ and refs/: a stray HEAD file must not move the root (and with it the
    # protected guard's kit.toml) into a subfolder.
    repo = make_repo(tmp_path)
    write(repo, "sub/.git/HEAD", "ref: refs/heads/main\n")
    write(repo, "sub/.git/config", "[core]\n\tbare = false\n")  # else the missing config alone asks git
    assert same(find_root(repo / "sub"), git_toplevel(repo / "sub"))
    assert same(find_root(repo / "sub"), repo)


def test_crossing_a_filesystem_boundary_asks_git(tmp_path, monkeypatch):
    # git stops at a mount point unless GIT_DISCOVERY_ACROSS_FILESYSTEM is set; the walk can't
    # tell what git would do there, so it asks.
    from kitlib import gitdisk

    repo = make_repo(tmp_path)
    (repo / "mounted").mkdir()
    monkeypatch.setattr(gitdisk, "_CHECK_DEVICE", True)
    monkeypatch.setattr(gitdisk, "_device", lambda folder: 2 if same(folder, repo / "mounted") else 1)
    assert gitdisk.toplevel(repo / "mounted") is gitdisk.UNKNOWN


def test_the_same_filesystem_is_answered_from_disk(tmp_path, monkeypatch):
    from kitlib import gitdisk

    repo = make_repo(tmp_path)
    (repo / "sub").mkdir()
    monkeypatch.setattr(gitdisk, "_CHECK_DEVICE", True)
    monkeypatch.setattr(gitdisk, "_device", lambda folder: 1)
    assert same(gitdisk.toplevel(repo / "sub"), repo)


def test_git_common_dir_in_the_environment_asks_git(tmp_path, monkeypatch):
    from kitlib import gitdisk

    repo = make_repo(tmp_path)  # first: git itself would obey the variable while building it
    monkeypatch.setenv("GIT_COMMON_DIR", str(tmp_path))
    assert gitdisk.toplevel(repo) is gitdisk.UNKNOWN


@pytest.mark.parametrize("inside", [".git", ".git/refs"])
def test_a_folder_inside_dot_git_is_no_working_tree(tmp_path, inside):
    repo = make_repo(tmp_path)
    assert lanes.locate(repo / inside) == (None, None)  # as git rev-parse answers there


def test_a_bare_repository_is_no_working_tree(tmp_path):
    bare = tmp_path / "bare repo.git"
    git(tmp_path, "init", "-q", "--bare", str(bare))
    assert lanes.locate(bare) == (None, None)


def test_core_worktree_in_a_separate_git_dir_sends_the_question_to_git(tmp_path):
    repo = make_repo(tmp_path)
    git(repo, "init", "-q", f"--separate-git-dir={tmp_path / 'git store'}")
    (repo / "elsewhere").mkdir()
    git(repo, "config", "core.worktree", str(repo / "elsewhere"))
    assert same(find_root(repo), git_toplevel(repo))


def test_per_worktree_config_sends_the_question_to_git(lane):
    git(lane, "config", "extensions.worktreeConfig", "true")
    git(lane, "config", "--worktree", "core.worktree", str(lane / "src"))
    assert same(find_root(lane), git_toplevel(lane))


@pytest.mark.parametrize(
    "line",
    ["\tbare = true", "\tbare", "[core] bare = true", "\tbare = true ; note", "\tBare=yes", "\tworktree = ../x"],
)
def test_config_lines_that_move_the_working_tree(tmp_path, line):
    from kitlib import gitdisk

    dot = tmp_path / ".git"
    write(tmp_path, ".git/config", f"[core]\n\trepositoryformatversion = 0\n{line}\n")
    assert gitdisk._moves_worktree(dot)


def test_an_ordinary_config_does_not_move_the_working_tree(tmp_path):
    from kitlib import gitdisk

    write(tmp_path, ".git/config", '[core]\n\tbare = false\n\tlogallrefupdates = true\n[remote "origin"]\n')
    assert not gitdisk._moves_worktree(tmp_path / ".git")


def test_a_dot_git_file_naming_a_folder_that_is_no_repository(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "sub/gd/HEAD", "ref: refs/heads/main\n")
    write(repo, "sub/.git", "gitdir: gd\n")
    assert same(find_root(repo / "sub"), repo)


def test_a_dot_git_whose_head_names_nothing_is_no_repository(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "sub/.git/HEAD", "not a ref\n")
    write(repo, "sub/.git/config", "[core]\n\tbare = false\n")
    (repo / "sub" / ".git" / "objects").mkdir()
    (repo / "sub" / ".git" / "refs").mkdir()
    assert same(find_root(repo / "sub"), git_toplevel(repo / "sub"))
    assert same(find_root(repo / "sub"), repo)


def test_the_protected_guard_still_blocks_from_under_a_fake_dot_git(tmp_path):
    # Both reviewers' round-1 repro: a hook cwd below a `.git` git rejects must still find the
    # project's kit.toml, so a protected path stays blocked.
    import json

    from helpers import RULES_TOML

    repo = make_repo(tmp_path, config=RULES_TOML + '\n[protected]\npaths = ["vendor/**"]\n')
    write(repo, "sub/.git/HEAD", "ref: refs/heads/main\n")
    write(repo, "sub/.git/config", "[core]\n\tbare = false\n")
    payload = {
        "cwd": str(repo / "sub"),
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(repo / "vendor" / "lib.py")},
    }
    result = run_cli(repo / "sub", "hook", "protected", stdin=json.dumps(payload))
    assert result.returncode == 2, result
