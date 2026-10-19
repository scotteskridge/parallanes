"""Claude Code's session lock on a lane worktree (decision 119, plan 14)."""

import os
import subprocess
import sys

import pytest

from helpers import git, run_cli
from kitlib import lanes, session_lock
from lane_helpers import lane_dir, lanes_repo


def finished_pid() -> int:
    """The pid of a process that has exited (and been reaped): what a leftover lock names."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


@pytest.mark.parametrize(
    "reason, expected",
    [
        ("claude session core (pid 123)", 123),
        ("claude session my lane (pid 7)", 7),  # git keeps the reason as written
        ("moving disk", None),  # an owner's own lock
        ("claude session core", None),
        ("claude session core (pid x)", None),
        ("", None),
        (None, None),
    ],
)
def test_only_claude_codes_reason_names_a_pid(reason, expected):
    assert session_lock.pid_of(reason) == expected


def test_this_process_is_running():
    assert session_lock.is_running(os.getpid()) is True


def test_a_finished_process_is_not_running():
    assert session_lock.is_running(finished_pid()) is False


def test_a_pid_that_cant_be_a_process_counts_as_running():
    # The cautious answer when the check can't tell (decision 119): never clear a lock on a guess.
    assert session_lock.is_running(0) is True


# ---- reading the lock from git ---------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    repo = lanes_repo(tmp_path)
    assert run_cli(repo, "lanes", "create", "core").returncode == 0
    return repo


def lock(repo, reason):
    git(repo, "worktree", "lock", "--reason", reason, str(lane_dir(repo, "core")))


@pytest.mark.slow
def test_find_reads_a_claude_code_lock_by_its_folder(repo):
    lock(repo, f"claude session core (pid {os.getpid()})")
    found = session_lock.find(repo, lane_dir(repo, "core"))
    assert found == session_lock.SessionLock(os.getpid(), running=True)
    assert session_lock.find(repo, lane_dir(repo, "api")) is None  # not created: no entry


@pytest.mark.slow
def test_find_ignores_an_owners_lock_and_an_unlocked_lane(repo):
    assert session_lock.find(repo, lane_dir(repo, "core")) is None
    lock(repo, "moving disk")
    assert session_lock.find(repo, lane_dir(repo, "core")) is None
    assert lanes.worktree_locks(repo)[0][1] is None  # the main checkout is never locked


@pytest.mark.slow
def test_a_lock_without_a_reason_is_read_as_no_session(repo):
    git(repo, "worktree", "lock", str(lane_dir(repo, "core")))
    assert session_lock.find(repo, lane_dir(repo, "core")) is None
