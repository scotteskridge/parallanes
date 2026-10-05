"""`kit lanes start <task>`: a fresh task branch, only once the previous one is proved merged (decisions 46, 47, 51)."""
import subprocess

import pytest

from helpers import git, run_cli, write
from lane_helpers import commit, cycle_repo, gh_calls, no_gh_env, scripted_gh


@pytest.fixture
def pr_lane(tmp_path):
    return cycle_repo(tmp_path)


def start(lane, *args, env=None):
    return run_cli(lane, "lanes", "start", *args, env=env)


def head(folder, ref="HEAD"):
    return git(folder, "rev-parse", ref).strip()


def branch(folder):
    return git(folder, "rev-parse", "--abbrev-ref", "HEAD").strip()


def has_branch(folder, name):
    return bool(git(folder, "branch", "--list", name).strip())


def on_task_with_work(lane, task="first"):
    """The lane on core/<task> with one commit of its own; returns that commit."""
    git(lane, "switch", "-q", "--no-track", "-c", f"core/{task}", "origin/main")
    return commit(lane, "src/core/work.py", "y = 2\n", "work")


def land_on_origin(repo, rel="src/api/other.py"):
    """Someone else's change reaches origin/main (pushed from the main checkout)."""
    commit(repo, rel, "z = 3\n", "other work")
    git(repo, "push", "-q", "origin", "main")
    return head(repo)


# ---- the new branch ------------------------------------------------------------------------------

def test_start_between_tasks_creates_the_branch_at_the_fetched_tip(pr_lane, tmp_path):
    repo, lane = pr_lane
    tip = land_on_origin(repo)  # the lane hasn't fetched it yet
    result = start(lane, "fix-login", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 0, result.stderr
    assert branch(lane) == "core/fix-login"
    assert head(lane) == tip
    assert "core/fix-login" in result.stdout


def test_new_branch_has_no_upstream(pr_lane, tmp_path):
    _, lane = pr_lane
    assert start(lane, "fix-login", env=scripted_gh(tmp_path / "gh")).returncode == 0
    result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "@{u}"], cwd=lane, capture_output=True, text=True)
    assert result.returncode != 0  # no upstream: decision 47


def test_local_mode_starts_from_the_local_integration_branch_without_fetching(tmp_path):
    repo, lane = cycle_repo(tmp_path, mode="local")
    local_tip = commit(repo, "src/api/local.py", "a = 1\n", "local only")  # detached main checkout
    git(repo, "branch", "-f", "main", local_tip)
    result = start(lane, "fix", env=no_gh_env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert head(lane) == local_tip


@pytest.mark.parametrize("slug", ["Fix", "-x", "a/b", "a b", "x" * 51, ""])
def test_bad_slug_is_refused(pr_lane, tmp_path, slug):
    _, lane = pr_lane
    result = start(lane, slug, env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 2
    assert "task" in result.stderr
    assert "Traceback" not in result.stderr


def test_existing_branch_name_is_refused(pr_lane, tmp_path):
    _, lane = pr_lane
    git(lane, "branch", "core/taken", "origin/main")
    result = start(lane, "taken", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 2
    assert "already exists" in result.stderr


def test_uncommitted_changes_are_refused(pr_lane, tmp_path):
    _, lane = pr_lane
    write(lane, "src/core/wip.py", "w = 1\n")
    result = start(lane, "next", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 2
    assert "uncommitted" in result.stderr
    assert (lane / "src/core/wip.py").is_file()


def test_outside_a_lane_is_refused(pr_lane, tmp_path):
    repo, _ = pr_lane
    result = start(repo, "next", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 2
    assert "not a lane" in result.stderr


def test_a_branch_that_is_not_a_task_branch_is_left_alone(pr_lane, tmp_path):
    _, lane = pr_lane
    git(lane, "switch", "-q", "-c", "experiment")
    result = start(lane, "next", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 2
    assert "experiment" in result.stderr
    assert branch(lane) == "experiment"


# ---- the previous branch -------------------------------------------------------------------------

def test_previous_branch_merged_by_ancestry_is_deleted(pr_lane, tmp_path):
    repo, lane = pr_lane
    on_task_with_work(lane)
    git(lane, "push", "-q", "origin", "HEAD:main")  # merged as a fast-forward
    result = start(lane, "second", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 0, result.stderr
    assert not has_branch(lane, "core/first")
    assert branch(lane) == "core/second"
    assert gh_calls(tmp_path / "gh") == []  # no need to ask


def test_squash_merged_pr_at_the_same_head_counts(pr_lane, tmp_path):
    repo, lane = pr_lane
    work = on_task_with_work(lane)
    tip = land_on_origin(repo, "src/core/work.py")  # a squash: same change, a different commit
    gh = tmp_path / "gh"
    env = scripted_gh(gh, prs=[{"number": 4, "state": "MERGED", "headRefOid": work, "url": "u4"}])
    result = start(lane, "second", env=env)
    assert result.returncode == 0, result.stderr
    assert not has_branch(lane, "core/first")
    assert head(lane) == tip
    assert any(call[:2] == ["pr", "list"] and "core/first" in call for call in gh_calls(gh))


@pytest.mark.parametrize("state, words", [("OPEN", "still open"), ("CLOSED", "closed without merging")])
def test_open_or_closed_pr_is_refused(pr_lane, tmp_path, state, words):
    _, lane = pr_lane
    work = on_task_with_work(lane)
    env = scripted_gh(tmp_path / "gh", prs=[{"number": 5, "state": state, "headRefOid": work, "url": "u5"}])
    result = start(lane, "second", env=env)
    assert result.returncode == 2
    assert words in result.stderr and "#5" in result.stderr
    assert "--abandon" in result.stderr
    assert branch(lane) == "core/first"


def test_merged_pr_at_an_older_commit_does_not_count(pr_lane, tmp_path):
    """A reused slug, or commits added after the PR merged (ARCHITECTURE §15)."""
    _, lane = pr_lane
    old = on_task_with_work(lane)
    commit(lane, "src/core/more.py", "m = 1\n", "more after the merge")
    env = scripted_gh(tmp_path / "gh", prs=[{"number": 3, "state": "MERGED", "headRefOid": old, "url": "u3"}])
    result = start(lane, "second", env=env)
    assert result.returncode == 2
    assert "#3" in result.stderr and "other commit" in result.stderr
    assert branch(lane) == "core/first"


def test_no_pr_is_refused(pr_lane, tmp_path):
    _, lane = pr_lane
    on_task_with_work(lane)
    result = start(lane, "second", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 2
    assert "no PR" in result.stderr


def test_without_gh_it_refuses_instead_of_guessing(pr_lane, tmp_path):
    _, lane = pr_lane
    on_task_with_work(lane)
    result = start(lane, "second", env=no_gh_env(tmp_path))
    assert result.returncode == 2
    assert "gh" in result.stderr
    assert branch(lane) == "core/first"


def test_local_mode_unmerged_branch_is_refused(tmp_path):
    _, lane = cycle_repo(tmp_path, mode="local")
    git(lane, "switch", "-q", "--no-track", "-c", "core/first", "main")
    commit(lane, "src/core/work.py", "y = 2\n", "work")
    result = start(lane, "second", env=no_gh_env(tmp_path))
    assert result.returncode == 2
    assert "lanes finish" in result.stderr


def test_abandon_drops_an_unmerged_branch_and_prints_its_sha(pr_lane, tmp_path):
    _, lane = pr_lane
    work = on_task_with_work(lane)
    result = start(lane, "second", "--abandon", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 0, result.stderr
    assert not has_branch(lane, "core/first")
    assert work in result.stdout
    assert branch(lane) == "core/second"


def test_leftover_task_branches_are_noted_not_deleted(pr_lane, tmp_path):
    _, lane = pr_lane
    git(lane, "branch", "core/old", "origin/main")
    git(lane, "branch", "api/theirs", "origin/main")
    result = start(lane, "next", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 0, result.stderr
    assert "core/old" in result.stdout
    assert "api/theirs" not in result.stdout
    assert has_branch(lane, "core/old")


def test_works_from_a_subfolder_of_the_lane(pr_lane, tmp_path):
    _, lane = pr_lane
    result = start(lane / "src" / "core", "deep", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 0, result.stderr
    assert branch(lane) == "core/deep"


# ---- from the first review -----------------------------------------------------------------------

def test_detached_commits_are_not_orphaned(pr_lane, tmp_path):
    _, lane = pr_lane
    orphan = commit(lane, "src/core/loose.py", "l = 1\n", "made between tasks")  # lane is detached
    result = start(lane, "next", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 2
    assert orphan[:12] in result.stderr and "--abandon" in result.stderr
    assert head(lane) == orphan


def test_abandon_detached_commits_prints_the_sha(pr_lane, tmp_path):
    _, lane = pr_lane
    orphan = commit(lane, "src/core/loose.py", "l = 1\n", "made between tasks")
    result = start(lane, "next", "--abandon", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 0, result.stderr
    assert orphan in result.stdout
    assert branch(lane) == "core/next"


def test_a_slug_still_on_origin_is_refused(pr_lane, tmp_path):
    """GitHub keeps head branches by default: a reused name would sync and push against the old one."""
    _, lane = pr_lane
    on_task_with_work(lane, "fix")
    git(lane, "push", "-q", "origin", "core/fix")
    git(lane, "switch", "-q", "--detach", "origin/main")
    git(lane, "branch", "-q", "-D", "core/fix")
    result = start(lane, "fix", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 2
    assert "origin/core/fix" in result.stderr


def test_merged_pr_whose_head_is_newer_than_the_local_tip_counts(pr_lane, tmp_path):
    """GitHub's "Update branch" or a web-UI commit added to the PR after the local tip."""
    repo, lane = pr_lane
    local = on_task_with_work(lane)
    newer = commit(lane, "src/core/web.py", "w = 1\n", "made on GitHub")
    git(lane, "push", "-q", "origin", "core/first")
    git(lane, "reset", "-q", "--hard", local)
    land_on_origin(repo, "src/core/work.py")  # the squash
    env = scripted_gh(tmp_path / "gh", prs=[{"number": 2, "state": "MERGED", "headRefOid": newer, "url": "u2"}])
    result = start(lane, "second", env=env)
    assert result.returncode == 0, result.stderr
    assert not has_branch(lane, "core/first")


# ---- from the second review ----------------------------------------------------------------------

def test_a_name_freed_on_origin_can_be_used_again(pr_lane, tmp_path):
    """GitHub's "automatically delete head branches": the stale remote-tracking ref is pruned."""
    repo, lane = pr_lane
    on_task_with_work(lane, "fix")
    git(lane, "push", "-q", "origin", "core/fix")
    git(lane, "switch", "-q", "--detach", "origin/main")
    git(lane, "branch", "-q", "-D", "core/fix")
    git(tmp_path / "origin repo.git", "branch", "-D", "core/fix")  # deleted on the server only
    result = start(lane, "fix", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 0, result.stderr
    assert branch(lane) == "core/fix"


def test_detached_commits_kept_on_a_branch_are_not_orphans(pr_lane, tmp_path):
    _, lane = pr_lane
    git(lane, "switch", "-q", "-c", "core/keep")
    kept = commit(lane, "src/core/keep.py", "k = 1\n", "kept")
    git(lane, "switch", "-q", "--detach", "core/keep")
    result = start(lane, "next", env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 0, result.stderr
    assert git(lane, "rev-parse", "core/keep").strip() == kept


def test_merged_pr_head_only_on_the_pull_ref_is_fetched(pr_lane, tmp_path):
    """Update branch on GitHub, squash, head branch deleted: the newer head lives only in refs/pull/<n>/head."""
    repo, lane = pr_lane
    local = on_task_with_work(lane)
    newer = commit(lane, "src/core/web.py", "w = 1\n", "made on GitHub")
    git(lane, "push", "-q", "origin", "HEAD:refs/pull/2/head")
    git(lane, "reset", "-q", "--hard", local)
    git(lane, "reflog", "expire", "--expire=now", "--all")
    git(lane, "gc", "-q", "--prune=now")
    land_on_origin(repo, "src/core/work.py")
    env = scripted_gh(tmp_path / "gh", prs=[{"number": 2, "state": "MERGED", "headRefOid": newer, "url": "u2"}])
    result = start(lane, "second", env=env)
    assert result.returncode == 0, result.stderr
