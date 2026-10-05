"""`kit lanes finish`: sync, run the tests, then open a PR or fast-forward (decisions 49, 50)."""
import pytest

from helpers import git, run_cli, write
from lane_helpers import commit, cycle_repo, gh_calls, no_gh_env, recorded_test_runs, scripted_gh

pytestmark = pytest.mark.slow  # real repos, worktrees and CLI processes: seconds a test on Windows


def on_task(lane, base="origin/main"):
    git(lane, "switch", "-q", "--no-track", "-c", "core/task", base)
    return commit(lane, "src/core/work.py", "y = 2\n", "Add the work")


def finish(lane, *args, env):
    return run_cli(lane, "lanes", "finish", *args, env=env)


def rev(folder, ref="HEAD"):
    return git(folder, "rev-parse", ref).strip()


def remote_branch(repo, name):
    return git(repo, "ls-remote", "origin", f"refs/heads/{name}").split()[:1]


# ---- PR mode -------------------------------------------------------------------------------------

@pytest.fixture
def pr_lane(tmp_path):
    repo, lane = cycle_repo(tmp_path)
    on_task(lane)
    return repo, lane


def test_pr_mode_tests_push_and_open_the_pr(pr_lane, tmp_path):
    repo, lane = pr_lane
    gh = tmp_path / "gh"
    result = finish(lane, env=scripted_gh(gh))
    assert result.returncode == 0, result.stderr
    assert recorded_test_runs(tmp_path) == [rev(lane)]
    assert remote_branch(repo, "core/task") == [rev(lane)]
    create = [call for call in gh_calls(gh) if call[:2] == ["pr", "create"]]
    assert len(create) == 1
    call = create[0]
    assert call[call.index("--base") + 1] == "main"
    assert call[call.index("--head") + 1] == "core/task"
    assert call[call.index("--title") + 1] == "Add the work"
    assert "https://github.com/o/r/pull/9" in result.stdout


def test_title_and_body_file_are_passed_on(pr_lane, tmp_path):
    _, lane = pr_lane
    body = tmp_path / "pr body.md"
    body.write_text("Plan: docs/plans/x.md\n", encoding="utf-8")
    gh = tmp_path / "gh"
    result = finish(lane, "--title", "Fix login", "--body-file", str(body), env=scripted_gh(gh))
    assert result.returncode == 0, result.stderr
    call = next(call for call in gh_calls(gh) if call[:2] == ["pr", "create"])
    assert call[call.index("--title") + 1] == "Fix login"
    assert call[call.index("--body-file") + 1] == str(body)


def test_missing_body_file_is_refused_before_anything_happens(pr_lane, tmp_path):
    repo, lane = pr_lane
    result = finish(lane, "--body-file", str(tmp_path / "nope.md"), env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 2
    assert "nope.md" in result.stderr
    assert recorded_test_runs(tmp_path) == []
    assert remote_branch(repo, "core/task") == []


def test_failing_tests_stop_before_any_push(pr_lane, tmp_path):
    repo, lane = pr_lane
    (tmp_path / "FAIL").write_text("", encoding="utf-8")
    gh = tmp_path / "gh"
    result = finish(lane, env=scripted_gh(gh))
    assert result.returncode == 1
    assert "tests failed (exit 1)" in result.stderr and recorded_test_runs(tmp_path)  # they ran, and failed
    assert remote_branch(repo, "core/task") == []
    assert gh_calls(gh) == []


def test_tests_run_on_the_synced_result(pr_lane, tmp_path):
    repo, lane = pr_lane
    commit(repo, "src/api/other.py", "z = 3\n", "other work")
    git(repo, "push", "-q", "origin", "main")
    result = finish(lane, env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 0, result.stderr
    assert git(lane, "merge-base", "--is-ancestor", rev(repo), "HEAD") == ""  # synced first
    assert recorded_test_runs(tmp_path) == [rev(lane)]


def test_rerun_with_an_open_pr_only_pushes(pr_lane, tmp_path):
    repo, lane = pr_lane
    git(lane, "push", "-q", "-u", "origin", "core/task")
    new = commit(lane, "src/core/fix.py", "f = 1\n", "Address review")
    gh = tmp_path / "gh"
    env = scripted_gh(gh, prs=[{"number": 7, "state": "OPEN", "headRefOid": "old", "url": "https://x/pull/7"}])
    result = finish(lane, env=env)
    assert result.returncode == 0, result.stderr
    assert remote_branch(repo, "core/task") == [new]
    assert not [call for call in gh_calls(gh) if call[:2] == ["pr", "create"]]
    assert "#7" in result.stdout


def test_without_gh_it_pushes_then_says_how_to_open_the_pr(pr_lane, tmp_path):
    repo, lane = pr_lane
    result = finish(lane, env=no_gh_env(tmp_path))
    assert result.returncode == 1
    assert remote_branch(repo, "core/task") == [rev(lane)]
    assert "core/task" in result.stderr and "open the PR" in result.stderr


def test_gh_create_failure_is_reported(pr_lane, tmp_path):
    repo, lane = pr_lane
    result = finish(lane, env=scripted_gh(tmp_path / "gh", create=None))
    assert result.returncode == 1
    assert "gh pr create" in result.stderr
    assert remote_branch(repo, "core/task") == [rev(lane)]


def test_nothing_ahead_is_refused(tmp_path):
    _, lane = cycle_repo(tmp_path)
    git(lane, "switch", "-q", "--no-track", "-c", "core/empty", "origin/main")
    result = finish(lane, env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 2
    assert "nothing to finish" in result.stderr
    assert recorded_test_runs(tmp_path) == []


def test_uncommitted_changes_are_refused(pr_lane, tmp_path):
    _, lane = pr_lane
    write(lane, "src/core/a.py", "x = 'edited, not committed'\n")
    result = finish(lane, env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 2
    assert "uncommitted" in result.stderr


def test_missing_test_command_is_refused(tmp_path):
    repo, lane = cycle_repo(tmp_path)
    on_task(lane)
    config = (lane / ".claude" / "kit.toml").read_text(encoding="utf-8")
    kept = [line for line in config.splitlines() if not line.startswith("test_command")]
    write(lane, ".claude/kit.toml", "\n".join(kept) + "\n")
    git(lane, "commit", "-q", "-am", "no tests")
    result = finish(lane, env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 2
    assert "test_command" in result.stderr


# ---- local mode ----------------------------------------------------------------------------------

@pytest.fixture
def local_lane(tmp_path):
    repo, lane = cycle_repo(tmp_path, mode="local")
    work = on_task(lane, base="main")
    return repo, lane, work


def test_local_mode_fast_forwards_then_leaves_the_lane_between_tasks(local_lane, tmp_path):
    repo, lane, work = local_lane
    result = finish(lane, env=no_gh_env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert rev(repo, "main") == work
    assert git(lane, "rev-parse", "--abbrev-ref", "HEAD").strip() == "HEAD"  # detached
    assert rev(lane) == work
    assert not git(lane, "branch", "--list", "core/task").strip()
    assert remote_branch(repo, "main") != [work]  # no network in local mode


def test_local_mode_refuses_while_the_main_checkout_holds_main(local_lane, tmp_path):
    repo, lane, work = local_lane
    git(repo, "switch", "-q", "main")
    result = finish(lane, env=no_gh_env(tmp_path))
    assert result.returncode == 2
    assert "git switch --detach main" in result.stderr
    assert recorded_test_runs(tmp_path) == []


def test_local_mode_race_resyncs_retests_and_retries_once(local_lane, tmp_path):
    repo, lane, work = local_lane
    other = commit(repo, "src/api/theirs.py", "t = 1\n", "another lane landed")  # detached, main not moved yet
    git(repo, "checkout", "-q", "--detach", "main")
    (tmp_path / "RACE").write_text(other, encoding="utf-8")
    result = finish(lane, env=no_gh_env(tmp_path))
    assert result.returncode == 0, result.stderr
    runs = recorded_test_runs(tmp_path)
    assert len(runs) == 2 and runs[0] == work and runs[1] != work
    assert rev(repo, "main") == runs[1]
    assert git(repo, "merge-base", "--is-ancestor", other, "main") == ""


def test_local_mode_failing_tests_leave_main_alone(local_lane, tmp_path):
    repo, lane, work = local_lane
    before = rev(repo, "main")
    (tmp_path / "FAIL").write_text("", encoding="utf-8")
    result = finish(lane, env=no_gh_env(tmp_path))
    assert result.returncode == 1 and "tests failed (exit 1)" in result.stderr and recorded_test_runs(tmp_path)
    assert rev(repo, "main") == before
    assert git(lane, "rev-parse", "--abbrev-ref", "HEAD").strip() == "core/task"


# ---- from the first review -----------------------------------------------------------------------

def test_outside_a_lane_or_between_tasks_is_refused(pr_lane, tmp_path):
    repo, lane = pr_lane
    assert "not a lane" in finish(repo, env=scripted_gh(tmp_path / "gh")).stderr
    git(lane, "switch", "-q", "--detach")
    result = finish(lane, env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 2
    assert "between tasks" in result.stderr


def test_a_test_command_that_moves_head_lands_nothing(pr_lane, tmp_path):
    repo, lane = pr_lane
    (tmp_path / "COMMIT").write_text("", encoding="utf-8")
    gh = tmp_path / "gh"
    result = finish(lane, env=scripted_gh(gh))
    assert result.returncode == 1
    assert "changed" in result.stderr and "Traceback" not in result.stderr
    assert remote_branch(repo, "core/task") == []
    assert gh_calls(gh) == []


def test_commits_dropped_by_the_sync_leave_nothing_to_finish(pr_lane, tmp_path):
    repo, lane = pr_lane
    commit(repo, "src/core/work.py", "y = 2\n", "the same change, landed by someone else")
    git(repo, "push", "-q", "origin", "main")
    result = finish(lane, env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 1  # the rebase rewrote the branch: unfinished, not "nothing changed"
    assert "already in" in result.stderr and "rebased" in result.stderr and "Traceback" not in result.stderr
    assert recorded_test_runs(tmp_path) == []
    assert remote_branch(repo, "core/task") == []


def test_steps_already_done_are_shown_when_the_tests_fail(pr_lane, tmp_path):
    repo, lane = pr_lane
    commit(repo, "src/api/other.py", "z = 3\n", "other work")
    git(repo, "push", "-q", "origin", "main")
    (tmp_path / "FAIL").write_text("", encoding="utf-8")
    result = finish(lane, env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 1
    assert "Rebased onto origin/main" in result.stdout
    assert result.stdout.index("Rebased") < result.stdout.index("fake tests ran")


def test_local_mode_with_a_backup_upstream_still_finishes_cleanly(local_lane, tmp_path):
    repo, lane, work = local_lane
    git(lane, "push", "-q", "-u", "origin", "core/task")
    work = commit(lane, "src/core/more.py", "m = 1\n", "after the backup")  # upstream is now behind
    result = finish(lane, env=no_gh_env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert rev(repo, "main") == work
    assert not git(lane, "branch", "--list", "core/task").strip()


def test_local_mode_refuses_while_another_lane_holds_main(local_lane, tmp_path):
    repo, lane, work = local_lane
    assert run_cli(repo, "lanes", "create", "api").returncode == 0
    git(repo / ".claude" / "worktrees" / "api", "switch", "-q", "main")
    result = finish(lane, env=no_gh_env(tmp_path))
    assert result.returncode == 2
    assert "api" in result.stderr and "main" in result.stderr
    assert recorded_test_runs(tmp_path) == []


# ---- from the second review ----------------------------------------------------------------------

def test_untracked_reports_from_the_tests_do_not_block(pr_lane, tmp_path):
    repo, lane = pr_lane
    (tmp_path / "REPORT").write_text("", encoding="utf-8")
    result = finish(lane, env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 0, result.stderr
    assert remote_branch(repo, "core/task") == [rev(lane)]


def test_a_test_command_that_edits_a_tracked_file_lands_nothing(pr_lane, tmp_path):
    repo, lane = pr_lane
    (tmp_path / "TOUCH").write_text("", encoding="utf-8")
    result = finish(lane, env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 1
    assert "changed" in result.stderr
    assert remote_branch(repo, "core/task") == []


def test_a_conflict_during_finish_is_unfinished(pr_lane, tmp_path):
    repo, lane = pr_lane
    commit(repo, "src/core/work.py", "y = 99\n", "conflicting")
    git(repo, "push", "-q", "origin", "main")
    result = finish(lane, env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 1
    assert "git rebase --continue" in result.stderr
    assert recorded_test_runs(tmp_path) == []


def test_local_mode_non_race_push_failure_is_not_retried(local_lane, tmp_path):
    repo, lane, work = local_lane
    hooks = repo / ".git" / "hooks"
    hook = hooks / "pre-receive"
    hook.write_text("#!/bin/sh\necho refused by policy >&2\nexit 1\n", encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    before = rev(repo, "main")
    result = finish(lane, env=no_gh_env(tmp_path))
    assert result.returncode == 1
    assert "refused by policy" in result.stderr
    assert len(recorded_test_runs(tmp_path)) == 1
    assert rev(repo, "main") == before


# ---- from the third review -----------------------------------------------------------------------

def test_local_mode_names_a_gone_worktree_that_still_holds_main(local_lane, tmp_path):
    import shutil

    repo, lane, work = local_lane
    other = tmp_path / "old checkout"
    git(repo, "worktree", "add", "-q", str(other), "main")
    shutil.rmtree(other)
    result = finish(lane, env=no_gh_env(tmp_path))
    assert result.returncode == 2
    assert "git worktree prune" in result.stderr
    assert recorded_test_runs(tmp_path) == []


# ---- untracked files: tracked changes refuse, untracked ones are a note (owner's call) ------------

def test_test_reports_do_not_block_the_next_finish(pr_lane, tmp_path):
    repo, lane = pr_lane
    (tmp_path / "REPORT").write_text("", encoding="utf-8")
    assert finish(lane, env=scripted_gh(tmp_path / "gh")).returncode == 0
    write(lane, "src/core/fix.py", "f = 1\n")
    git(lane, "add", "src/core/fix.py")  # not `add -A`: junit.xml must stay out
    git(lane, "commit", "-q", "-m", "Address review")
    new = rev(lane)
    result = finish(lane, env=scripted_gh(tmp_path / "gh"))
    assert result.returncode == 0, result.stderr
    assert remote_branch(repo, "core/task") == [new]
    assert "junit.xml" in result.stdout and ".gitignore" in result.stdout


def test_start_after_a_local_finish_with_test_reports(local_lane, tmp_path):
    repo, lane, work = local_lane
    (tmp_path / "REPORT").write_text("", encoding="utf-8")
    assert finish(lane, env=no_gh_env(tmp_path)).returncode == 0
    result = run_cli(lane, "lanes", "start", "next", env=no_gh_env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "junit.xml" in result.stdout


def test_the_note_warns_that_untracked_files_are_tested_but_do_not_land(local_lane, tmp_path):
    """A forgotten `git add`: the tests see the file, the integration branch won't get it."""
    repo, lane, work = local_lane
    write(lane, "src/core/helper.py", "h = 1\n")
    result = finish(lane, env=no_gh_env(tmp_path))
    assert "src/core/helper.py" in result.stdout
    assert "won't land" in result.stdout and "git add" in result.stdout
