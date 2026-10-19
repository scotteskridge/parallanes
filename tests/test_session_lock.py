"""Claude Code's session lock on a lane worktree (decision 119, plan 14)."""

import os

import pytest

from helpers import git, run_cli
from kitlib import lanes, session_lock
from lane_helpers import finished_process, lane_dir, lanes_repo, lock_lane


@pytest.mark.parametrize(
    "reason, expected",
    [
        ("claude session core (pid 123)", 123),
        ("claude session my lane (pid 7)", 7),  # git keeps the reason as written
        ("claude session core (pid 99999999999999999999)", 99999999999999999999),  # judged by is_running
        ("moving disk", None),  # an owner's own lock
        ("claude session core", None),
        ("claude session core (pid x)", None),
        ("claude session core (pid ١٢٣)", None),  # only ASCII digits: \d also takes other scripts'
        ("", None),
        (None, None),
    ],
)
def test_only_claude_codes_reason_names_a_pid(reason, expected):
    assert session_lock.pid_of(reason) == expected


def test_this_process_is_running():
    assert session_lock.is_running(os.getpid()) is True


def test_a_finished_process_is_not_running():
    ended = finished_process()
    assert session_lock.is_running(ended.pid) is False


@pytest.mark.parametrize("pid", [0, -1, -4242, 2**31, 10**30])
def test_a_pid_that_cant_be_one_process_counts_as_running(pid):
    # The cautious answer when the check can't tell (decision 119): never clear a lock on a guess.
    # Review round 1: os.kill raised OverflowError on POSIX.
    assert session_lock.is_running(pid) is True


def test_a_pid_past_32_bits_isnt_cut_down_to_another_process():
    # Review round 1: Windows' DWORD argument turned 2**32 + n into n, so it checked process n.
    ended = finished_process()
    assert session_lock.is_running(2**32 + ended.pid) is True  # can't tell: running, not "gone"


# ---- reading the lock from git ---------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    repo = lanes_repo(tmp_path)
    assert run_cli(repo, "lanes", "create", "core").returncode == 0
    return repo


def lock_of(repo, name):
    return next(reason for path, reason in lanes.worktree_locks(repo) if lanes.same_path(path, lane_dir(repo, name)))


@pytest.mark.slow
def test_find_reads_a_claude_code_lock_by_its_folder(repo):
    lock_lane(repo, "core", f"claude session core (pid {os.getpid()})")
    found = session_lock.find(repo, lane_dir(repo, "core"))
    assert found == session_lock.SessionLock(os.getpid(), running=True)
    assert session_lock.find(repo, lane_dir(repo, "api")) is None  # not created: no entry


@pytest.mark.slow
def test_find_ignores_an_owners_lock_and_an_unlocked_lane(repo):
    assert session_lock.find(repo, lane_dir(repo, "core")) is None
    assert lock_of(repo, "core") is None
    lock_lane(repo, "core", "moving disk")
    assert lock_of(repo, "core") == "moving disk"
    assert session_lock.find(repo, lane_dir(repo, "core")) is None
    assert lanes.worktree_locks(repo)[0][1] is None  # the main checkout is never locked


@pytest.mark.slow
def test_a_lock_without_a_reason_is_read_as_no_session(repo):
    git(repo, "worktree", "lock", str(lane_dir(repo, "core")))
    assert lock_of(repo, "core") == ""  # locked, no reason: not None
    assert session_lock.find(repo, lane_dir(repo, "core")) is None
