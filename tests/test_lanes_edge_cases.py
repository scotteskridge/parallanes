"""Lane edge cases found by the second review: reruns, odd repository layouts, merge detection, messages."""
import json
import shutil
import subprocess
import sys

import pytest

from helpers import CLI, RULES_TOML, git, make_repo, run_cli, write
from kitlib import lane_setup, lanes
from kitlib.config import load
from lane_helpers import LANES_TOML, commit, lane_dir, lanes_repo

pytestmark = pytest.mark.slow  # real repos, worktrees and CLI processes: seconds a test on Windows


@pytest.fixture
def repo(tmp_path):
    return lanes_repo(tmp_path)


def create(repo, *args):
    return run_cli(repo, "lanes", "create", *args)


def brief(folder):
    payload = json.dumps({"cwd": str(folder), "hook_event_name": "SessionStart", "source": "startup"})
    result = run_cli(folder, "hook", "lane-router", stdin=payload)
    assert result.returncode == 0, result.stderr
    return result.stdout


def ownership(cwd, target):
    payload = json.dumps({"cwd": str(cwd), "hook_event_name": "PreToolUse", "tool_name": "Edit",
                          "tool_input": {"file_path": str(target)}})
    return run_cli(cwd, "hook", "ownership", stdin=payload)


def ignore(repo, *patterns):
    write(repo, ".gitignore", "\n".join([".claude/worktrees/", ".env", ".claude/settings.local.json", *patterns]) + "\n")
    git(repo, "commit", "-q", "-am", "ignore more")
    git(repo, "push", "-q")


# ---- create ------------------------------------------------------------------------------------

def test_rerun_copies_include_files_a_failed_run_missed(repo, monkeypatch):
    write(repo, ".worktreeinclude", ".env\n.claude/settings.local.json\n")
    write(repo, ".env", "A=1\n")
    write(repo, ".claude/settings.local.json", '{"from main": 1}')
    real = shutil.copy2

    def fail(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(shutil, "copy2", fail)
    with pytest.raises(lanes.LaneError):
        lane_setup.create(repo, load(repo), ["core"])
    monkeypatch.setattr(shutil, "copy2", real)
    write(lane_dir(repo, "core"), ".claude/settings.local.json", '{"mine": 1}')  # never overwritten
    lane_setup.create(repo, load(repo), ["core"])
    assert (lane_dir(repo, "core") / ".env").read_text() == "A=1\n"
    local = json.loads((lane_dir(repo, "core") / ".claude/settings.local.json").read_text(encoding="utf-8"))
    assert local["mine"] == 1 and "from main" not in local


def test_a_failed_worktree_add_is_not_reported_as_created(repo):
    assert create(repo, "api").returncode == 0
    git(repo, "worktree", "lock", str(lane_dir(repo, "api")))
    shutil.rmtree(lane_dir(repo, "api"))
    result = create(repo)
    assert result.returncode == 2
    assert "api: created" not in result.stdout
    assert "core: created" in result.stdout
    assert "api:" in result.stderr


def test_a_leftover_folder_fails_only_its_lane(repo):
    write(repo, ".claude/worktrees/core/notes.txt", "mine\n")
    result = create(repo)
    assert result.returncode == 2
    assert "api: created" in result.stdout
    assert "core:" in result.stderr and "not this lane's worktree" in result.stderr


# ---- remove ------------------------------------------------------------------------------------

def test_remove_after_create_with_an_included_folder(repo):
    ignore(repo, "secrets/")
    write(repo, ".worktreeinclude", "secrets/\n")
    write(repo, "secrets/key.txt", "k\n")
    write(repo, "secrets/deep/more.txt", "m\n")
    assert create(repo, "core").returncode == 0
    result = run_cli(repo, "lanes", "remove", "core")
    assert result.returncode == 0, result.stderr


def test_remove_refuses_new_work_in_an_included_folder(repo):
    ignore(repo, "secrets/")
    write(repo, ".worktreeinclude", "secrets/\n")
    write(repo, "secrets/key.txt", "k\n")
    assert create(repo, "core").returncode == 0
    write(lane_dir(repo, "core"), "secrets/new.txt", "work\n")
    result = run_cli(repo, "lanes", "remove", "core")
    assert result.returncode == 2 and "secrets/" in result.stderr


def test_remove_does_not_count_caches(repo):
    ignore(repo, "__pycache__/", ".pytest_cache/")
    assert create(repo, "core").returncode == 0
    write(lane_dir(repo, "core"), "src/core/__pycache__/a.cpython-311.pyc", "x")
    write(lane_dir(repo, "core"), ".pytest_cache/v/cache/lastfailed", "{}")
    result = run_cli(repo, "lanes", "remove", "core")
    assert result.returncode == 0, result.stderr


# ---- repository layouts ------------------------------------------------------------------------

def test_separate_git_dir_named_dot_git_is_not_mistaken_for_the_main_checkout(tmp_path):
    repo = lanes_repo(tmp_path, origin=False)
    (tmp_path / "store").mkdir()
    git(repo, "init", "-q", f"--separate-git-dir={tmp_path / 'store' / '.git'}")
    assert create(repo, "core").returncode == 2  # refused
    git(repo, "worktree", "add", "-q", "--detach", str(lane_dir(repo, "core")))  # made by hand anyway
    with pytest.raises(lanes.LaneError):
        lanes.current_lane(lane_dir(repo, "core"), load(repo))


def test_lane_of_a_submodule(tmp_path, repo):
    outer = tmp_path / "outer"
    outer.mkdir()
    git(outer, "init", "-q", "-b", "main")
    git(outer, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(repo), "inner")
    inner = outer / "inner"
    assert create(inner, "core").returncode == 0
    lane = inner / ".claude" / "worktrees" / "core"
    assert lanes.main_checkout(lane).resolve() == inner.resolve()
    assert lanes.current_lane(lane, load(inner)).name == "core"


def test_broken_lane_code_does_not_break_the_protected_guard(tmp_path):
    kit = tmp_path / "kit copy"
    shutil.copytree(CLI.parent, kit, ignore=shutil.ignore_patterns("__pycache__"))
    with open(kit / "kitlib" / "lanes.py", "a", encoding="utf-8") as handle:
        handle.write("\nraise RuntimeError('broken lanes')\n")
    project = make_repo(tmp_path, config=RULES_TOML + '\n[protected]\npaths = ["vendor/**"]\n')

    def run(*args, stdin=""):
        return subprocess.run([sys.executable, str(kit / "cli.py"), *args], cwd=project, input=stdin,
                              capture_output=True, text=True, encoding="utf-8")

    payload = json.dumps({"cwd": str(project), "hook_event_name": "PreToolUse", "tool_name": "Write",
                          "tool_input": {"file_path": str(project / "vendor" / "x.py")}})
    assert run("hook", "protected", stdin=payload).returncode == 2
    result = run("lanes", "status")
    assert result.returncode == 2
    assert "broken lanes" in result.stderr and "Traceback" not in result.stderr


# ---- merge detection ---------------------------------------------------------------------------

@pytest.fixture
def task(repo):
    assert create(repo, "core").returncode == 0
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/task")
    return folder


def test_work_reset_away_is_not_merged(task):
    commit(task, "src/core/b.py", "y = 1\n")
    git(task, "reset", "-q", "--hard", "origin/main")
    assert "already merged" not in brief(task)


def test_branch_name_reused_with_switch_force_is_not_merged(task):
    commit(task, "src/core/b.py", "y = 1\n")
    git(task, "switch", "-q", "--detach")
    git(task, "switch", "-q", "-C", "core/task", "origin/main")
    assert "already merged" not in brief(task)


def test_applied_patch_counts_as_own_work(task, tmp_path):
    commit(task, "src/core/b.py", "y = 1\n")
    (tmp_path / "p.patch").write_text(git(task, "format-patch", "-1", "--stdout"), encoding="utf-8")
    git(task, "reset", "-q", "--hard", "HEAD~1")
    git(task, "am", "-q", str(tmp_path / "p.patch"))
    git(task, "push", "-q", "origin", "core/task:main")
    git(task, "fetch", "-q")
    assert "already merged" in brief(task)


def test_local_mode_does_not_mention_fetch(tmp_path):
    config = LANES_TOML.replace('integration_branch = "main"', 'integration_branch = "main"\nmerge_mode = "local"')
    repo = lanes_repo(tmp_path, config=config)
    assert create(repo, "core").returncode == 0
    commit(repo, "src/api/b.py", "y = 2\n")
    text = brief(lane_dir(repo, "core"))
    assert "behind main" in text and "fetch" not in text


# ---- ownership messages ------------------------------------------------------------------------

@pytest.fixture
def lane(repo):
    assert create(repo).returncode == 0
    return lane_dir(repo, "core")


def test_other_lane_message_reads_well(lane, repo):
    result = ownership(lane, lane_dir(repo, "api") / "src/core/x.py")
    reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "the folder of lane 'api'" in reason and "''s" not in reason


def test_main_checkout_git_folder_has_its_own_reason(lane, repo):
    result = ownership(lane, repo / ".git" / "config")
    reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "git data" in reason and "copy here" not in reason


# ---- from the third review ---------------------------------------------------------------------

def test_cache_names_inside_work_paths_still_count(repo):
    ignore(repo, "*.secret", "node_modules")
    assert create(repo, "core").returncode == 0
    folder = lane_dir(repo, "core")
    write(folder, "src/venv/keys.secret", "k\n")  # `venv` here is a work folder, not a virtualenv
    write(folder, "notes/node_modules", "a file, not the cache folder\n")
    result = run_cli(repo, "lanes", "remove", "core")
    assert result.returncode == 2
    assert "src/venv/keys.secret" in result.stderr and "notes/node_modules" in result.stderr


def test_unreadable_file_counts_as_work_without_a_traceback(repo, monkeypatch):
    from kitlib import lane_setup

    ignore(repo, "*.secret")
    assert create(repo, "core").returncode == 0
    write(lane_dir(repo, "core"), "locked.secret", "x\n")
    write(repo, "locked.secret", "x\n")

    def denied(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(lane_setup, "_identical_files", denied)
    assert "locked.secret" in lane_setup.ignored_work(repo, lane_dir(repo, "core"))


def test_main_checkout_without_the_kit_names_the_cause(repo):
    assert create(repo, "core").returncode == 0
    git(repo, "rm", "-q", ".claude/kit.toml")
    git(repo, "commit", "-q", "-m", "before the kit")  # as if the main checkout were on an old commit
    with pytest.raises(lanes.LaneError, match="no .claude/kit.toml"):
        lanes.locate(lane_dir(repo, "core"))


def test_create_refuses_a_layout_lanes_cannot_work_in(tmp_path):
    repo = lanes_repo(tmp_path, origin=False)
    git(repo, "init", "-q", f"--separate-git-dir={tmp_path / 'proj.git'}")
    result = create(repo)
    assert result.returncode == 2
    assert "separate git dir" in result.stderr
    assert "core: created" not in result.stdout
    assert not lane_dir(repo, "core").exists()
    assert "worktrees" not in git(repo, "worktree", "list")


def test_registered_lane_with_a_deleted_folder_says_prune(repo):
    assert create(repo, "api").returncode == 0
    shutil.rmtree(lane_dir(repo, "api"))
    for args in ((), ("--dry-run",)):
        result = create(repo, *args)
        assert result.returncode == 2
        assert "git worktree prune" in result.stderr
        assert "api: would create" not in result.stdout


def test_old_git_output_is_an_error_not_silence(monkeypatch, repo):
    monkeypatch.setattr(lanes, "git", lambda *args, **kwargs: "--path-format=absolute\n/a\n/b\n/c\n")
    with pytest.raises(lanes.LaneError, match="git 2.36"):
        lanes.locate(repo)
