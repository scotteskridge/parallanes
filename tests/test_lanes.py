"""`kit lanes create / status / remove` on throwaway repos with a bare origin (decisions 35-39, 42, 43)."""

import json
import os

import pytest

from helpers import git, run_cli, write
from kitlib import lane_setup, lanes
from kitlib.config import load
from lane_helpers import LANES_TOML, commit, fake_gh, lane_dir, lanes_repo, no_gh_env

pytestmark = pytest.mark.slow  # real repos, worktrees and CLI processes: seconds a test on Windows


@pytest.fixture
def repo(tmp_path):
    return lanes_repo(tmp_path)


def create(repo, *args, cwd=None):
    result = run_cli(cwd or repo, "lanes", "create", *args)
    return result


def head(folder):
    return git(folder, "rev-parse", "HEAD").strip()


# ---- create ------------------------------------------------------------------------------------


def test_create_makes_detached_worktrees_at_the_integration_tip(repo):
    result = create(repo)
    assert result.returncode == 0, result.stderr
    for name in ("core", "api"):
        folder = lane_dir(repo, name)
        assert (folder / "src" / "core" / "a.py").is_file()
        assert git(folder, "rev-parse", "--abbrev-ref", "HEAD").strip() == "HEAD"  # detached
        assert head(folder) == head(repo)
        assert name in result.stdout


def test_create_prefers_origin_over_the_local_branch(repo):
    origin_tip = head(repo)
    commit(repo, "local.txt", "not pushed\n")  # local main is now ahead of origin/main
    assert create(repo, "core").returncode == 0
    assert head(lane_dir(repo, "core")) == origin_tip


def test_create_uses_the_local_branch_without_origin(tmp_path):
    repo = lanes_repo(tmp_path, origin=False)
    assert create(repo, "core").returncode == 0
    assert head(lane_dir(repo, "core")) == head(repo)


def test_create_named_lanes_only(repo):
    assert create(repo, "api").returncode == 0
    assert lane_dir(repo, "api").is_dir()
    assert not lane_dir(repo, "core").exists()


def test_create_unknown_lane_is_an_error(repo):
    result = create(repo, "uii")
    assert result.returncode == 2
    assert "uii" in result.stderr and "core" in result.stderr
    assert not (repo / ".claude" / "worktrees").exists()


def test_create_is_idempotent(repo):
    assert create(repo).returncode == 0
    again = create(repo)
    assert again.returncode == 0, again.stderr
    assert "already" in again.stdout


def test_create_refuses_a_nested_root_that_is_not_ignored(tmp_path):
    repo = lanes_repo(tmp_path, ignore=False)
    result = create(repo)
    assert result.returncode == 2
    assert ".gitignore" in result.stderr and ".claude/worktrees/" in result.stderr
    assert not (repo / ".claude" / "worktrees").exists()
    assert ".claude/worktrees" not in (repo / ".gitignore").read_text()  # never edits the file


def test_create_refuses_a_folder_that_is_not_the_lanes_worktree(repo):
    write(repo, ".claude/worktrees/core/notes.txt", "mine\n")
    result = create(repo, "core")
    assert result.returncode == 2
    assert "core" in result.stderr and "not" in result.stderr
    assert (lane_dir(repo, "core") / "notes.txt").read_text() == "mine\n"


def test_create_copies_ignored_worktreeinclude_files_only(repo):
    write(repo, ".worktreeinclude", ".env\n.claude/settings.local.json\nsrc/core/a.py\nmissing.txt\n")
    git(repo, "add", ".worktreeinclude")
    git(repo, "commit", "-q", "-m", "include")
    git(repo, "push", "-q")
    write(repo, ".env", "SECRET=1\n")
    write(repo, ".claude/settings.local.json", '{"env": {"A": "1"}}\n')
    write(repo, "src/core/a.py", "x = 'edited, tracked'\n")
    write(repo, "untracked.txt", "not ignored, not listed\n")
    assert create(repo, "core").returncode == 0
    folder = lane_dir(repo, "core")
    assert (folder / ".env").read_text() == "SECRET=1\n"
    assert (folder / "src/core/a.py").read_text() == "x = 1\n"  # tracked: the committed version
    assert not (folder / "untracked.txt").exists()
    local = json.loads((folder / ".claude/settings.local.json").read_text(encoding="utf-8"))
    assert local["env"] == {"A": "1"}  # copied, then the exclusion merged in


def test_create_does_not_copy_other_lanes_files(repo):
    write(repo, ".worktreeinclude", ".env\n")
    assert create(repo, "core").returncode == 0
    write(lane_dir(repo, "core"), ".env", "core's own\n")
    assert create(repo, "api").returncode == 0
    assert not (lane_dir(repo, "api") / ".env").exists()


def test_create_excludes_the_main_checkouts_instructions(repo):
    assert create(repo, "core").returncode == 0
    local = json.loads((lane_dir(repo, "core") / ".claude/settings.local.json").read_text(encoding="utf-8"))
    excluded = local["claudeMdExcludes"]
    for name in ("CLAUDE.md", "AGENTS.md", ".claude/CLAUDE.md"):
        assert str((repo / name).resolve()).replace("\\", "/") in excluded
    # Never the lane's own copies.
    assert not any(str(lane_dir(repo, "core").resolve()).replace("\\", "/") in entry for entry in excluded)


def test_exclusion_merges_with_existing_settings_and_keeps_style(repo):
    write(repo, ".worktreeinclude", ".claude/settings.local.json\n")
    write(
        repo,
        ".claude/settings.local.json",
        '{\r\n    "claudeMdExcludes": ["/elsewhere/CLAUDE.md"],\r\n    "x": 1\r\n}\r\n',
    )
    assert create(repo, "core").returncode == 0
    raw = (lane_dir(repo, "core") / ".claude/settings.local.json").read_bytes()
    assert b'\r\n    "x": 1' in raw
    data = json.loads(raw)
    assert data["claudeMdExcludes"][0] == "/elsewhere/CLAUDE.md"
    assert len(data["claudeMdExcludes"]) == 4


def test_unreadable_local_settings_are_left_alone_and_reported(repo):
    write(repo, ".worktreeinclude", ".claude/settings.local.json\n")
    write(repo, ".claude/settings.local.json", "{ not json")
    result = create(repo, "core")
    assert result.returncode == 2
    assert "settings.local.json" in result.stderr
    assert (lane_dir(repo, "core") / ".claude/settings.local.json").read_text() == "{ not json"


def test_sibling_root_with_project_placeholder(tmp_path):
    config = LANES_TOML.replace(
        'integration_branch = "main"', 'integration_branch = "main"\nworktree_root = "../{project}-lanes"'
    )
    repo = lanes_repo(tmp_path, config=config)
    assert create(repo, "core").returncode == 0
    folder = tmp_path / "demo-lanes" / "core"
    assert (folder / "src/core/a.py").is_file()
    # Not nested: nothing of the main checkout's is loaded, so nothing is excluded.
    assert not (folder / ".claude/settings.local.json").exists()


def test_dry_run_changes_nothing(repo):
    result = create(repo, "--dry-run")
    assert result.returncode == 0
    assert "core" in result.stdout and "api" in result.stdout
    assert not (repo / ".claude" / "worktrees").exists()
    assert "worktrees" not in git(repo, "worktree", "list")


def test_create_works_from_inside_a_lane(repo):
    assert create(repo, "core").returncode == 0
    assert create(repo, "api", cwd=lane_dir(repo, "core") / "src").returncode == 0
    assert lane_dir(repo, "api").is_dir()
    assert not (lane_dir(repo, "core") / ".claude" / "worktrees").exists()


def test_create_without_lanes_says_so(tmp_path):
    repo = lanes_repo(tmp_path, config=LANES_TOML.split("[[lanes]]")[0])
    result = create(repo)
    assert result.returncode == 2
    assert "[[lanes]]" in result.stderr


# ---- lane lookup -------------------------------------------------------------------------------


def test_current_lane_from_main_lane_and_subfolder(repo):
    assert create(repo).returncode == 0
    config = load(repo)
    assert lanes.current_lane(repo, config) is None
    assert lanes.current_lane(lane_dir(repo, "core"), config).name == "core"
    sub = lane_dir(repo, "api") / "src" / "core"
    assert lanes.current_lane(sub, config).name == "api"
    assert lanes.main_checkout(sub).resolve() == repo.resolve()


@pytest.mark.skipif(os.name != "nt", reason="Windows paths are case-insensitive")
def test_current_lane_ignores_case_on_windows(repo):
    assert create(repo, "core").returncode == 0
    upper = type(repo)(str(lane_dir(repo, "core")).upper())
    assert lanes.current_lane(upper, load(repo)).name == "core"


def test_a_folder_that_is_not_a_lane(tmp_path, repo):
    other = tmp_path / "elsewhere"
    git(repo, "worktree", "add", "-q", "--detach", str(other))
    assert lanes.current_lane(other, load(repo)) is None


# ---- remove ------------------------------------------------------------------------------------


def test_remove_deletes_the_worktree(repo):
    assert create(repo, "core").returncode == 0
    result = run_cli(repo, "lanes", "remove", "core")
    assert result.returncode == 0, result.stderr
    assert not lane_dir(repo, "core").exists()
    assert "core" not in git(repo, "worktree", "list")


def test_remove_refuses_uncommitted_changes(repo):
    assert create(repo, "core").returncode == 0
    write(lane_dir(repo, "core"), "src/core/a.py", "x = 2\n")
    result = run_cli(repo, "lanes", "remove", "core")
    assert result.returncode == 2
    assert "uncommitted" in result.stderr
    assert lane_dir(repo, "core").is_dir()


def test_remove_refuses_untracked_files(repo):
    assert create(repo, "core").returncode == 0
    write(lane_dir(repo, "core"), "new.py", "y = 1\n")
    assert run_cli(repo, "lanes", "remove", "core").returncode == 2
    assert (lane_dir(repo, "core") / "new.py").is_file()


def test_remove_a_lane_that_was_never_created(repo):
    result = run_cli(repo, "lanes", "remove", "core")
    assert result.returncode == 2
    assert "not created" in result.stderr


def test_remove_refuses_the_lane_it_runs_in(repo):
    assert create(repo, "core").returncode == 0
    result = run_cli(lane_dir(repo, "core"), "lanes", "remove", "core")
    assert result.returncode == 2
    assert lane_dir(repo, "core").is_dir()


# ---- status ------------------------------------------------------------------------------------


def status(repo, *args, env=None, cwd=None):
    return run_cli(cwd or repo, "lanes", "status", *args, env=env or no_gh_env(repo))


def lane_line(output, name):
    return next(line for line in output.splitlines() if line.startswith(name + " "))


def test_status_before_create(repo):
    result = status(repo)
    assert result.returncode == 0, result.stderr
    assert "not created" in lane_line(result.stdout, "core")


def test_status_between_tasks(repo):
    assert create(repo).returncode == 0
    line = lane_line(status(repo).stdout, "core")
    assert "detached" in line and "between tasks" in line
    assert ".claude/worktrees/core" in line


def test_status_counts_untracked_files_apart(repo):
    """Decision 52: untracked files (a test report) aren't unfinished work; /next relies on this."""
    assert create(repo, "core").returncode == 0
    write(lane_dir(repo, "core"), "junit.xml", "<testsuite/>\n")
    line = lane_line(status(repo).stdout, "core")
    assert "1 untracked" in line and "changed" not in line and "uncommitted" not in line


def test_status_reports_branch_ahead_behind_dirty_unpushed(repo):
    assert create(repo, "core").returncode == 0
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/login")
    commit(folder, "src/core/b.py", "y = 1\n")
    commit(folder, "src/core/c.py", "z = 1\n")
    write(folder, "src/core/a.py", "x = 3\n")
    commit(repo, "README.md", "moved on\n")
    git(repo, "push", "-q")
    git(repo, "fetch", "-q")
    line = lane_line(status(repo).stdout, "core")
    assert "core/login" in line
    assert "2 ahead" in line and "1 behind" in line and "origin/main" in line
    assert "1 changed" in line and "untracked" not in line
    assert "not pushed" in line
    assert "PR: unknown" in line


def test_status_counts_unpushed_commits(repo):
    assert create(repo, "core").returncode == 0
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/login")
    commit(folder, "src/core/b.py", "y = 1\n")
    git(folder, "push", "-q", "-u", "origin", "core/login")
    commit(folder, "src/core/c.py", "z = 1\n")
    assert "1 unpushed" in lane_line(status(repo).stdout, "core")


def test_status_says_when_a_pushed_branch_is_gone_from_origin(tmp_path, repo):
    """Usually its PR merged and GitHub deleted the head branch; "not pushed" would mislead."""
    assert create(repo, "core").returncode == 0
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/login")
    commit(folder, "src/core/b.py", "y = 1\n")
    git(folder, "push", "-q", "-u", "origin", "core/login")
    git(tmp_path / "origin repo.git", "branch", "-D", "core/login")
    git(folder, "fetch", "-q", "--prune", "origin")
    line = lane_line(status(repo).stdout, "core")
    assert "gone from origin" in line and "not pushed" not in line


def test_status_shows_pr_state_from_gh(tmp_path, repo):
    assert create(repo, "core").returncode == 0
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/login")
    tip = git(folder, "rev-parse", "HEAD").strip()
    pr = {"number": 7, "state": "OPEN", "url": "https://example.test/7", "headRefOid": tip, "baseRefName": "main"}
    assert "PR #7 OPEN" in lane_line(status(repo, env=fake_gh(tmp_path / "bin", [pr])).stdout, "core")


def test_status_ignores_an_old_pr_for_a_reused_branch_name(tmp_path, repo):
    """Found in plan 05's live check: a reused slug showed the earlier branch's merged PR."""
    assert create(repo, "core").returncode == 0
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/login")
    old = commit(folder, "src/core/old.py", "o = 1\n")
    git(folder, "switch", "-q", "--detach", "origin/main")
    git(folder, "branch", "-q", "-D", "core/login")
    git(folder, "switch", "-q", "-c", "core/login")  # the same name, new work
    commit(folder, "src/core/new.py", "n = 1\n")
    pr = {"number": 1, "state": "MERGED", "url": "u1", "headRefOid": old, "baseRefName": "main"}
    line = lane_line(status(repo, env=fake_gh(tmp_path / "bin", [pr])).stdout, "core")
    assert "PR: none" in line and "#1" not in line


@pytest.mark.parametrize("new_work", [False, True])
def test_status_ignores_an_old_pr_merged_with_a_merge_commit(tmp_path, repo, new_work):
    """GitHub's default merge: the old PR's head is inside main, so every new branch contains it."""
    assert create(repo, "core").returncode == 0
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/login")
    old = commit(folder, "src/core/old.py", "o = 1\n")
    git(repo, "merge", "-q", "--no-ff", "-m", "Merge PR #1", "core/login")
    git(repo, "push", "-q", "origin", "main")
    git(folder, "fetch", "-q", "origin")
    git(folder, "switch", "-q", "--detach", "origin/main")
    git(folder, "branch", "-q", "-D", "core/login")
    git(folder, "switch", "-q", "-c", "core/login")
    if new_work:
        commit(folder, "src/core/new.py", "n = 1\n")
    pr = {"number": 1, "state": "MERGED", "url": "u1", "headRefOid": old, "baseRefName": "main"}
    line = lane_line(status(repo, env=fake_gh(tmp_path / "bin", [pr])).stdout, "core")
    assert "PR: none" in line and "#1" not in line


def test_status_shows_an_open_pr_whose_head_is_not_fetched(tmp_path, repo):
    assert create(repo, "core").returncode == 0
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/login")
    commit(folder, "src/core/b.py", "y = 1\n")
    pr = {"number": 5, "state": "OPEN", "url": "u5", "headRefOid": "c" * 40, "baseRefName": "main"}
    assert "PR #5 OPEN (head not fetched)" in lane_line(
        status(repo, env=fake_gh(tmp_path / "bin", [pr])).stdout, "core"
    )


def test_status_shows_a_pr_the_lane_has_added_commits_to(tmp_path, repo):
    assert create(repo, "core").returncode == 0
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/login")
    pushed = commit(folder, "src/core/a2.py", "a = 2\n")
    commit(folder, "src/core/a3.py", "a = 3\n")  # not pushed yet
    pr = {"number": 4, "state": "OPEN", "url": "u4", "headRefOid": pushed, "baseRefName": "main"}
    assert "PR #4 OPEN" in lane_line(status(repo, env=fake_gh(tmp_path / "bin", [pr])).stdout, "core")


def test_status_when_gh_fails_or_finds_nothing(tmp_path, repo):
    assert create(repo, "core").returncode == 0
    git(lane_dir(repo, "core"), "switch", "-q", "-c", "core/login")
    failing = status(repo, env=fake_gh(tmp_path / "bad", None))
    assert failing.returncode == 0
    assert "PR: unknown" in lane_line(failing.stdout, "core")
    assert "PR: none" in lane_line(status(repo, env=fake_gh(tmp_path / "none", [])).stdout, "core")


def test_status_offline_skips_gh(tmp_path, repo):
    assert create(repo, "core").returncode == 0
    git(lane_dir(repo, "core"), "switch", "-q", "-c", "core/login")
    env = fake_gh(tmp_path / "bin", [{"number": 7, "state": "OPEN", "url": "u"}])
    line = lane_line(status(repo, "--offline", env=env).stdout, "core")
    assert "PR #7" not in line and "PR: unknown" in line


def test_status_reports_the_main_checkout(repo):
    result = status(repo)
    assert "Main checkout" in result.stdout and "main" in result.stdout
    assert "local mode" not in result.stdout


def test_status_warns_in_local_mode_when_main_holds_the_integration_branch(tmp_path):
    config = LANES_TOML.replace('integration_branch = "main"', 'integration_branch = "main"\nmerge_mode = "local"')
    repo = lanes_repo(tmp_path, config=config)
    result = status(repo)
    assert "git switch --detach main" in result.stdout
    git(repo, "switch", "-q", "--detach", "main")
    assert "git switch --detach" not in status(repo).stdout


def test_status_notes_overlapping_lanes(tmp_path):
    config = LANES_TOML.replace('owns = ["src/api/**"]', 'owns = ["src/**"]')
    repo = lanes_repo(tmp_path, config=config)
    output = status(repo).stdout
    assert "Note: lanes core and api may overlap: src/core/** and src/**" in output


def test_status_has_no_overlap_note_for_separate_lanes(repo):
    assert "may overlap" not in status(repo).stdout


def test_status_from_inside_a_lane_marks_it(repo):
    assert create(repo).returncode == 0
    output = status(repo, cwd=lane_dir(repo, "api")).stdout
    assert "(this folder)" in lane_line(output, "api")
    assert "(this folder)" not in lane_line(output, "core")


def test_status_with_a_lane_folder_removed_by_hand(repo):
    import shutil

    assert create(repo, "core").returncode == 0
    shutil.rmtree(lane_dir(repo, "core"))
    result = status(repo)
    assert result.returncode == 0
    assert "missing" in lane_line(result.stdout, "core")


def test_lanes_commands_report_a_broken_config(tmp_path):
    repo = lanes_repo(tmp_path)
    write(repo, ".claude/kit.toml", LANES_TOML.replace('name = "api"', 'name = "API"'))
    for command in ("create", "status", "remove", "start", "sync", "finish"):
        args = ["lanes", command] + (["api"] if command in ("remove", "start") else [])
        result = run_cli(repo, *args)
        assert result.returncode == 2
        assert "'API'" in result.stderr and "Traceback" not in result.stderr


# ---- from the first review ---------------------------------------------------------------------


def test_local_mode_creates_from_the_local_branch(tmp_path):
    config = LANES_TOML.replace('integration_branch = "main"', 'integration_branch = "main"\nmerge_mode = "local"')
    repo = lanes_repo(tmp_path, config=config)
    tip = commit(repo, "src/api/b.py", "y = 2\n")  # not pushed: local mode doesn't use origin
    result = create(repo, "core")
    assert "detached at main" in result.stdout
    assert head(lane_dir(repo, "core")) == tip


def test_remove_refuses_ignored_work_unless_forced(repo):
    assert create(repo, "core").returncode == 0
    write(lane_dir(repo, "core"), ".env", "SECRET=work-in-progress\n")
    result = run_cli(repo, "lanes", "remove", "core")
    assert result.returncode == 2
    assert ".env" in result.stderr and "--force" in result.stderr
    assert (lane_dir(repo, "core") / ".env").is_file()
    forced = run_cli(repo, "lanes", "remove", "core", "--force")
    assert forced.returncode == 0, forced.stderr
    assert not lane_dir(repo, "core").exists()


def test_remove_ignores_files_create_put_there(repo):
    write(repo, ".worktreeinclude", ".env\n")
    write(repo, ".env", "A=1\n")
    assert create(repo, "core").returncode == 0  # copies .env and writes settings.local.json
    result = run_cli(repo, "lanes", "remove", "core")
    assert result.returncode == 0, result.stderr


def test_remove_reports_a_changed_local_settings_file(repo):
    assert create(repo, "core").returncode == 0
    path = lane_dir(repo, "core") / ".claude/settings.local.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["permissions"] = {"allow": ["Bash(make *)"]}
    path.write_text(json.dumps(data), encoding="utf-8")
    result = run_cli(repo, "lanes", "remove", "core")
    assert result.returncode == 2 and "settings.local.json" in result.stderr


def test_separate_git_dir_works_from_the_main_checkout_and_fails_clearly_in_a_lane(tmp_path):
    # git lists the git dir, not the working tree, as the main worktree here: nothing to trace back.
    repo = lanes_repo(tmp_path, origin=False)
    git(repo, "init", "-q", f"--separate-git-dir={tmp_path / 'git store'}")
    assert create(repo, "core").returncode == 2  # refused: its hooks couldn't find their way back
    git(repo, "worktree", "add", "-q", "--detach", str(lane_dir(repo, "core")))  # made by hand anyway
    assert status(repo).returncode == 0
    assert lanes.main_checkout(repo).resolve() == repo.resolve()
    with pytest.raises(lanes.LaneError, match="separate git dir"):
        lanes.current_lane(lane_dir(repo, "core"), load(repo))


def test_submodule_is_its_own_main_checkout(tmp_path, repo):
    outer = tmp_path / "outer"
    outer.mkdir()
    git(outer, "init", "-q", "-b", "main")
    git(outer, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(repo), "inner")
    inner = outer / "inner"
    assert lanes.main_checkout(inner / "src").resolve() == inner.resolve()


@pytest.mark.parametrize("response", [{"message": "rate limited"}, ["x"], [{"number": None}], "text"])
def test_status_survives_odd_gh_output(tmp_path, repo, response):
    assert create(repo, "core").returncode == 0
    git(lane_dir(repo, "core"), "switch", "-q", "-c", "core/t")
    result = status(repo, env=fake_gh(tmp_path / "bin", response))
    assert result.returncode == 0, result.stderr
    assert "PR: unknown" in lane_line(result.stdout, "core")


def test_create_reports_every_lane_and_finishes_the_rest_after_an_error(repo):
    write(repo, ".worktreeinclude", ".claude/settings.local.json\n")
    write(repo, ".claude/settings.local.json", "{ not json")
    first = create(repo)
    assert first.returncode == 2
    assert "core: created" in first.stdout and "api: created" in first.stdout
    assert first.stderr.count("settings.local.json") == 2
    # Fixed by hand, a rerun finishes the step it missed.
    for name in ("core", "api"):
        write(lane_dir(repo, name), ".claude/settings.local.json", "{}")
    second = create(repo)
    assert second.returncode == 0, second.stderr
    local = json.loads((lane_dir(repo, "core") / ".claude/settings.local.json").read_text(encoding="utf-8"))
    assert len(local["claudeMdExcludes"]) == 3


def test_copy_error_is_reported_not_a_traceback(repo, monkeypatch):
    import shutil

    write(repo, ".worktreeinclude", ".env\n")
    write(repo, ".env", "A=1\n")

    def fail(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(shutil, "copy2", fail)
    with pytest.raises(lanes.LaneError) as caught:
        lane_setup.create(repo, load(repo))
    assert "denied" in str(caught.value) and ".env" in str(caught.value)
    assert lane_dir(repo, "api").is_dir()  # the other lane was still created
