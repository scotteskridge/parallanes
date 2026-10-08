"""The lane-router SessionStart hook: briefs the agent, warns about drift, never blocks (decision 40)."""

import json

import pytest

from helpers import git, run_cli, write
from lane_helpers import LANES_TOML, PACKAGE_JSON, commit, lane_dir, lanes_repo

pytestmark = pytest.mark.slow  # real repos, worktrees and CLI processes: seconds a test on Windows


def session_start(cwd, source="startup"):
    payload = {"session_id": "t", "cwd": str(cwd), "hook_event_name": "SessionStart", "source": source}
    return run_cli(cwd, "hook", "lane-router", stdin=json.dumps(payload))


@pytest.fixture
def repo(tmp_path):
    repo = lanes_repo(tmp_path)
    assert run_cli(repo, "lanes", "create").returncode == 0
    return repo


def brief(folder, source="startup"):
    result = session_start(folder, source)
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stdout + result.stderr
    return result.stdout


def test_briefing_between_tasks(repo):
    text = brief(lane_dir(repo, "core"))
    assert "Lane: core" in text
    assert "Scope: Domain logic and its tests" in text
    assert "Owns: src/core/**, tests/core/**" in text
    assert "Resources: dev_port = 8001" in text
    assert "detached" in text
    assert "sh .claude/kit/parallanes lanes start" in text
    assert len(text.splitlines()) <= 15
    # Decision 97: a broad lane learns that nested lanes' files aren't its own before it edits them.
    assert "A file another lane's more specific pattern matches is that lane's" in text


def test_the_briefing_says_to_work_in_this_folder_not_the_main_checkout(repo):
    # Backlog lane-guide-trial-notes (trial F7): an agent dropped the worktree part of its folder and
    # read the main checkout's copy of a skill. Folded into the first line: the briefing has a cap.
    first = brief(lane_dir(repo, "core")).splitlines()[0]
    assert first.startswith("Lane: core (this folder is its worktree: ")
    assert first.endswith("; read and edit files here, not in the main checkout above it)")


def test_a_lane_beside_the_main_checkout_gets_no_above_it_clause(tmp_path):
    # Review: "above it" would be false for a lane outside the main checkout, which has no F7 trap.
    config = LANES_TOML.replace(
        'integration_branch = "main"', 'integration_branch = "main"\nworktree_root = "../{project}-lanes"'
    )
    repo = lanes_repo(tmp_path, config=config)
    assert run_cli(repo, "lanes", "create", "core").returncode == 0
    folder = tmp_path / "demo-lanes" / "core"
    first = brief(folder).splitlines()[0]
    assert first.startswith("Lane: core (this folder is its worktree: ") and first.endswith("core)")
    assert "main checkout" not in first


@pytest.mark.parametrize("source", ["startup", "resume", "clear", "compact"])
def test_every_source_gets_the_briefing(repo, source):
    assert "Lane: core" in brief(lane_dir(repo, "core"), source)


def test_from_a_subfolder_of_the_lane(repo):
    assert "Lane: api" in brief(lane_dir(repo, "api") / "src")


def test_clean_task_branch_has_no_warnings(repo):
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/login")
    text = brief(folder)
    assert "Branch: core/login" in text
    assert "Warnings" not in text


def test_branch_outside_the_lane_prefix(repo):
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "api/login")
    assert "not a core/<task> branch" in brief(folder)


def test_behind_the_integration_tip(repo):
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/login")
    commit(repo, "README.md", "new\n")
    git(repo, "push", "-q")
    assert "1 commit(s) behind origin/main" in brief(folder)


def test_already_merged_branch(repo):
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/login")
    commit(folder, "src/core/b.py", "y = 1\n")
    git(folder, "push", "-q", "origin", "core/login:main")  # as a merge would
    git(folder, "fetch", "-q")
    assert "already merged" in brief(folder)


def test_fresh_branch_is_not_reported_as_merged(repo):
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/login")
    commit(repo, "README.md", "new\n")
    git(repo, "push", "-q")  # the tip moved on; the fresh branch is an ancestor but did nothing
    assert "already merged" not in brief(folder)


def test_uncommitted_changes(repo):
    folder = lane_dir(repo, "core")
    write(folder, "src/core/a.py", "x = 9\n")
    assert "1 uncommitted change(s) to tracked files" in brief(folder)


def test_untracked_files_are_not_called_uncommitted_changes(repo):
    """Decision 52: a test report left behind isn't unfinished work."""
    folder = lane_dir(repo, "core")
    write(folder, "junit.xml", "<testsuite/>\n")
    text = brief(folder)
    assert "uncommitted" not in text
    assert "1 untracked file(s)" in text


def test_kit_toml_differs_from_the_integration_branch(repo):
    commit(repo, ".claude/kit.toml", LANES_TOML + '\n[[lanes]]\nname = "ui"\nowns = ["ui/**"]\n')
    git(repo, "push", "-q")
    assert "kit.toml differs from origin/main" in brief(lane_dir(repo, "core"))


def test_line_endings_alone_are_not_a_difference(repo):
    folder = lane_dir(repo, "core")
    path = folder / ".claude" / "kit.toml"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert "kit.toml differs" not in brief(folder)


def test_main_checkout_is_not_a_lane(repo):
    text = brief(repo)
    assert "not a lane" in text and "core, api" in text
    assert len(text.splitlines()) == 1


def test_silent_without_the_kit(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    git(plain, "init", "-q")
    assert brief(plain) == ""


def test_silent_without_lanes(tmp_path):
    assert brief(lanes_repo(tmp_path, config=LANES_TOML.split("[[lanes]]")[0])) == ""


def test_broken_config_tells_the_agent(repo):
    folder = lane_dir(repo, "core")
    write(folder, ".claude/kit.toml", "[project\n")
    text = brief(folder)
    assert "Lane check failed" in text and "sh .claude/kit/parallanes lanes status" in text


@pytest.mark.parametrize("stdin", ["not json", "[]", ""])
def test_bad_input_never_blocks(repo, stdin):
    result = run_cli(repo, "hook", "lane-router", stdin=stdin)
    assert result.returncode == 0
    assert "Lane check failed" in result.stdout
    assert "Traceback" not in result.stdout + result.stderr


# ---- from the first review ---------------------------------------------------------------------


def test_fresh_branch_fast_forwarded_is_not_merged(repo):
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/task")
    commit(repo, "src/api/b.py", "y = 2\n")
    git(repo, "push", "-q", "origin", "main")
    git(folder, "merge", "-q", "--ff-only", "origin/main")  # what syncing a fresh branch does
    assert "already merged" not in brief(folder)


def test_amended_and_merged_branch_is_reported(repo):
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "core/task")
    commit(folder, "src/core/b.py", "y = 1\n")
    git(folder, "commit", "-q", "--amend", "-m", "amended")
    git(folder, "push", "-q", "origin", "core/task:main")
    git(folder, "fetch", "-q")
    assert "already merged" in brief(folder)


def test_local_mode_measures_against_the_local_branch(tmp_path):
    config = LANES_TOML.replace('integration_branch = "main"', 'integration_branch = "main"\nmerge_mode = "local"')
    repo = lanes_repo(tmp_path, config=config)
    assert run_cli(repo, "lanes", "create", "core").returncode == 0
    commit(repo, "src/api/b.py", "y = 2\n")  # local main moves on; origin isn't used in local mode
    assert "1 commit(s) behind main" in brief(lane_dir(repo, "core"))


def test_worst_case_briefing_stays_in_budget(tmp_path):
    config = LANES_TOML.replace(
        'scope = "Domain logic and its tests"', 'scope = """Domain logic\nand its tests\nand more\nlines"""'
    ).replace('integration_branch = "main"', 'integration_branch = "main"\nshared_paths = ["docs/**"]')
    repo = lanes_repo(tmp_path, config=config)
    assert run_cli(repo, "lanes", "create", "core").returncode == 0
    folder = lane_dir(repo, "core")
    git(folder, "switch", "-q", "-c", "api/task")  # wrong lane prefix
    commit(folder, "src/core/b.py", "y = 1\n")
    git(folder, "push", "-q", "origin", "api/task:main")  # merged
    commit(repo, "README.md", "x\n")  # and behind
    git(repo, "pull", "-q", "--no-rebase", "--no-edit")
    commit(repo, ".claude/kit.toml", config + "\n# changed\n")  # kit.toml drift
    git(repo, "push", "-q")
    write(folder, "src/core/a.py", "dirty\n")  # uncommitted
    write(folder, "package.json", PACKAGE_JSON)  # untracked, and a Node lane without node_modules
    git(folder, "fetch", "-q")
    text = brief(folder)
    for word in (
        "not a core/<task>",
        "already merged",
        "behind",
        "kit.toml differs",
        "uncommitted",
        "untracked",
        "node_modules",
    ):
        assert word in text, text
    assert "Scope: Domain logic and its tests and more lines" in text
    assert len(text.splitlines()) <= 15, text


def test_crash_inside_the_router_tells_the_agent(monkeypatch, capsys, repo):
    import io
    import sys

    from kitlib import hooks, lane_hooks

    def boom(cwd):
        raise RuntimeError("injected")

    monkeypatch.setattr(lane_hooks, "router_text", boom)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"cwd": str(repo)})))
    assert hooks.run_lane_router() == 0
    out = capsys.readouterr().out
    assert "Lane check failed (RuntimeError: injected)" in out
