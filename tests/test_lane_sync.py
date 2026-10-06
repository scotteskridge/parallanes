"""`kit lanes sync`: rebase before the branch is pushed, merge after, stop on conflicts (decision 48)."""

from pathlib import Path

import pytest
from helpers import git, run_cli, write
from lane_helpers import commit, cycle_repo, no_gh_env

pytestmark = pytest.mark.slow  # real repos, worktrees and CLI processes: seconds a test on Windows


@pytest.fixture
def pr_lane(tmp_path):
    repo, lane = cycle_repo(tmp_path)
    git(lane, "switch", "-q", "--no-track", "-c", "core/task", "origin/main")
    commit(lane, "src/core/work.py", "y = 2\n", "work")
    return repo, lane


def sync(lane, tmp_path):
    return run_cli(lane, "lanes", "sync", env=no_gh_env(tmp_path))


def land_on_origin(repo, rel="src/api/other.py", text="z = 3\n"):
    commit(repo, rel, text, "other work")
    git(repo, "push", "-q", "origin", "main")
    return git(repo, "rev-parse", "HEAD").strip()


def parents(folder):
    return git(folder, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:]


def test_unpushed_branch_is_rebased_onto_the_fetched_tip(pr_lane, tmp_path):
    repo, lane = pr_lane
    tip = land_on_origin(repo)
    result = sync(lane, tmp_path)
    assert result.returncode == 0, result.stderr
    assert parents(lane) == [tip]  # linear: rebased
    assert "rebase" in result.stdout.lower()


def test_pushed_branch_is_merged_never_rewritten(pr_lane, tmp_path):
    repo, lane = pr_lane
    git(lane, "push", "-q", "-u", "origin", "core/task")
    pushed = git(lane, "rev-parse", "HEAD").strip()
    tip = land_on_origin(repo)
    result = sync(lane, tmp_path)
    assert result.returncode == 0, result.stderr
    assert parents(lane) == [pushed, tip]  # a merge commit on top of what was pushed
    assert "merge" in result.stdout.lower()


def test_already_up_to_date(pr_lane, tmp_path):
    _, lane = pr_lane
    before = git(lane, "rev-parse", "HEAD").strip()
    result = sync(lane, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "up to date" in result.stdout
    assert git(lane, "rev-parse", "HEAD").strip() == before


def test_conflict_is_left_in_progress_with_the_commands(pr_lane, tmp_path):
    repo, lane = pr_lane
    land_on_origin(repo, "src/core/work.py", "y = 99\n")
    result = sync(lane, tmp_path)
    assert result.returncode == 1  # work is mid-way: unfinished, not refused
    assert "src/core/work.py" in result.stderr
    assert "git rebase --continue" in result.stderr and "git rebase --abort" in result.stderr
    rebase_dir = git(lane, "rev-parse", "--path-format=absolute", "--git-path", "rebase-merge").strip()
    assert Path(rebase_dir).is_dir()  # still in progress: resolving it is the agent's work


def test_sync_refuses_while_a_rebase_is_in_progress(pr_lane, tmp_path):
    repo, lane = pr_lane
    land_on_origin(repo, "src/core/work.py", "y = 99\n")
    sync(lane, tmp_path)
    result = sync(lane, tmp_path)
    assert result.returncode == 2
    assert "in progress" in result.stderr


def test_merge_conflict_names_the_merge_commands(pr_lane, tmp_path):
    repo, lane = pr_lane
    git(lane, "push", "-q", "-u", "origin", "core/task")
    land_on_origin(repo, "src/core/work.py", "y = 99\n")
    result = sync(lane, tmp_path)
    assert result.returncode == 1
    assert "git merge --continue" in result.stderr and "git merge --abort" in result.stderr


def test_uncommitted_changes_are_refused(pr_lane, tmp_path):
    _, lane = pr_lane
    write(lane, "src/core/a.py", "x = 'edited, not committed'\n")
    result = sync(lane, tmp_path)
    assert result.returncode == 2
    assert "uncommitted" in result.stderr


def test_between_tasks_is_refused(tmp_path):
    _, lane = cycle_repo(tmp_path)
    result = sync(lane, tmp_path)
    assert result.returncode == 2
    assert "between tasks" in result.stderr


def test_local_mode_rebases_onto_the_local_branch(tmp_path):
    repo, lane = cycle_repo(tmp_path, mode="local")
    git(lane, "switch", "-q", "--no-track", "-c", "core/task", "main")
    commit(lane, "src/core/work.py", "y = 2\n", "work")
    tip = commit(repo, "src/api/x.py", "x = 1\n", "landed")  # main checkout is detached
    git(repo, "branch", "-f", "main", tip)
    result = sync(lane, tmp_path)
    assert result.returncode == 0, result.stderr
    assert parents(lane) == [tip]


def test_outside_a_lane_is_refused(pr_lane, tmp_path):
    repo, _ = pr_lane
    result = sync(repo, tmp_path)
    assert result.returncode == 2
    assert "not a lane" in result.stderr
