"""What the installer offers after the questions (plan 16, decisions 122 and 123).

With the lanes profile it shows a guess at the lanes and writes it into kit.toml on a yes. On a
clean repository with a commit, it offers to commit its own files, then to create the lanes. It
never pushes, and `--yes` and `--dry-run` never write lanes or commit.
"""

import subprocess
import sys
import tomllib

import pytest

from helpers import ROOT, git

SETUP = ROOT / "kit_setup.py"
pytestmark = pytest.mark.slow

ADD = "Add these lanes to .claude/kit.toml?"
COMMIT = "Commit the kit's files now?"
CREATE = "Create the lane folders now?"


def setup(target, *args, stdin=None):
    argv = [sys.executable, str(SETUP), "--target", str(target), *args]
    result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", input=stdin)
    return result


def project(tmp_path, commit=True):
    """A repository with two code folders, committed unless commit is False."""
    repo = tmp_path / "my project"
    (repo / "server").mkdir(parents=True)
    (repo / "public").mkdir()
    (repo / "server" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "public" / "index.html").write_text("<p></p>\n", encoding="utf-8")
    git_init(repo)
    git(repo, "add", "-A")
    if commit:
        git(repo, "commit", "-q", "-m", "first")
    return repo


def git_init(repo):
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    git(repo, "config", "user.name", "test")
    git(repo, "config", "user.email", "test@example.com")


def lanes_of(repo):
    config = tomllib.loads((repo / ".claude" / "kit.toml").read_text(encoding="utf-8"))
    return {lane["name"]: lane["owns"] for lane in config.get("lanes", [])}


# Answers in the order asked: five values, the profile, the pre-commit check, then the offers.
FIRST = "\n" * 5 + "y\n" + "y\n"


def test_lanes_all_the_way_to_lane_folders(tmp_path):
    repo = project(tmp_path)
    result = setup(repo, stdin=FIRST + "y\n" + "y\n" + "y\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert ADD in result.stdout and COMMIT in result.stdout and CREATE in result.stdout
    assert lanes_of(repo) == {"public": ["public/**"], "server": ["server/**"]}
    assert git(repo, "log", "-1", "--format=%s").strip() == "Add parallanes"
    assert git(repo, "status", "--porcelain").strip() == ""
    for lane in ("server", "public"):
        assert (repo / ".claude" / "worktrees" / lane / "server" / "app.py").is_file()
    # Next steps say how to open each lane, and no longer ask for what was just done.
    assert "claude" in result.stdout.split("Next:")[1]
    assert "Commit the kit's files" not in result.stdout.split("Next:")[1]


def test_declined_lanes_are_not_written_and_the_next_steps_say_how(tmp_path):
    repo = project(tmp_path)
    result = setup(repo, stdin=FIRST + "n\n" + "n\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert lanes_of(repo) == {}
    assert "lanes suggest" in result.stdout.split("Next:")[1]
    assert CREATE not in result.stdout  # no lanes to create
    assert git(repo, "log", "-1", "--format=%s").strip() == "first"


def test_no_commit_offer_when_the_tree_had_changes(tmp_path):
    repo = project(tmp_path)
    (repo / "notes.txt").write_text("mine\n", encoding="utf-8")
    result = setup(repo, stdin=FIRST + "y\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert COMMIT not in result.stdout
    assert git(repo, "log", "-1", "--format=%s").strip() == "first"


def test_no_commit_offer_before_the_first_commit(tmp_path):
    repo = project(tmp_path, commit=False)
    result = setup(repo, stdin=FIRST + "y\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert COMMIT not in result.stdout


@pytest.mark.parametrize("flags", [["--yes", "--profile", "lanes"], ["--dry-run", "--profile", "lanes"]])
def test_yes_and_dry_run_show_the_guess_but_write_no_lanes_and_commit_nothing(tmp_path, flags):
    repo = project(tmp_path)
    result = setup(repo, *flags)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'name = "server"' in result.stdout
    assert ADD not in result.stdout and COMMIT not in result.stdout
    assert git(repo, "log", "-1", "--format=%s").strip() == "first"
    if "--yes" in flags:
        assert lanes_of(repo) == {}


def test_with_an_origin_it_commits_but_never_pushes_and_says_to_push_first(tmp_path):
    repo = project(tmp_path)
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")
    result = setup(repo, stdin=FIRST + "y\n" + "y\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(repo, "log", "-1", "--format=%s").strip() == "Add parallanes"
    assert CREATE not in result.stdout
    assert git(origin, "log", "-1", "--format=%s", "main").strip() == "first"  # not pushed
    assert "Push the kit's commit to origin, then run" in result.stdout.split("Next:")[1]


def test_switching_a_solo_install_to_lanes_adds_the_lanes_to_the_owners_kit_toml(tmp_path):
    repo = project(tmp_path)
    assert setup(repo, "--yes").returncode == 0
    toml = repo / ".claude" / "kit.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + "# my note\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "kit")

    result = setup(repo, "--profile", "lanes", stdin="y\n" + "y\n" + "n\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "# my note" in toml.read_text(encoding="utf-8")
    assert set(lanes_of(repo)) == {"server", "public"}
    assert git(repo, "status", "--porcelain").strip() == ""  # committed


# ---- review round 1 ------------------------------------------------------------------------


def test_untracked_files_git_status_hides_are_never_committed(tmp_path):
    repo = project(tmp_path)
    (repo / "private-notes.txt").write_text("mine\n", encoding="utf-8")
    git(repo, "config", "status.showUntrackedFiles", "no")
    result = setup(repo, stdin=FIRST + "y\n" + "y\n" + "n\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "private-notes.txt" not in git(repo, "log", "--name-only", "--format=")
    assert COMMIT not in result.stdout


def test_the_commit_holds_only_what_the_install_wrote(tmp_path):
    repo = project(tmp_path)
    result = setup(repo, stdin=FIRST + "y\n" + "y\n" + "n\n")
    assert result.returncode == 0, result.stdout + result.stderr
    committed = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert ".claude/kit.toml" in committed and ".claude/settings.json" in committed
    assert not [path for path in committed if path.startswith(("server/", "public/"))]


@pytest.mark.parametrize("move", [["checkout", "-q", "-b", "feature"], ["checkout", "-q", "--detach"]])
def test_no_commit_offer_off_the_integration_branch(tmp_path, move):
    repo = project(tmp_path)
    git(repo, *move)
    result = setup(repo, stdin=FIRST + "y\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert COMMIT not in result.stdout
    assert git(repo, "log", "-1", "--format=%s").strip() == "first"


def test_no_commit_offer_in_a_subfolder_of_a_repository(tmp_path):
    repo = project(tmp_path)
    app = repo / "app"
    app.mkdir()
    result = setup(app, stdin="\n" * 5 + "y\n")  # no pre-commit question below the root
    assert result.returncode == 0, result.stdout + result.stderr
    assert COMMIT not in result.stdout
    assert "isn't the root of a git repository" in result.stdout


def test_a_rerun_with_nothing_new_offers_nothing_and_lists_the_lane_folders(tmp_path):
    repo = project(tmp_path)
    assert setup(repo, stdin=FIRST + "y\n" + "y\n" + "y\n").returncode == 0
    again = setup(repo, stdin="")
    assert again.returncode == 0, again.stdout + again.stderr
    assert COMMIT not in again.stdout and ADD not in again.stdout
    steps = again.stdout.split("Next:")[1]
    assert ".claude/worktrees/server" in steps and "lanes create" not in steps
    assert "Commit the kit's files" not in steps  # review round 2: it is committed


def test_no_commit_offer_when_the_owners_gitignore_covers_a_kit_path(tmp_path):
    repo = project(tmp_path)
    (repo / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-q", "-m", "ignore")
    result = setup(repo, stdin=FIRST + "y\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert COMMIT not in result.stdout and "The commit failed" not in result.stderr
    assert "No commit offered: your .gitignore ignores" in result.stdout


def test_a_rerun_that_adds_lanes_commits_them_as_an_update(tmp_path):
    repo = project(tmp_path)
    assert setup(repo, stdin="\n" * 5 + "n\n" + "y\n" + "y\n").returncode == 0  # solo, committed
    result = setup(repo, "--profile", "lanes", stdin="y\n" + "y\n" + "n\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(repo, "log", "-1", "--format=%s").strip() == "Update parallanes"


def test_input_closing_at_the_create_question_keeps_the_commit_and_says_so(tmp_path):
    repo = project(tmp_path)
    result = setup(repo, stdin=FIRST + "y\n" + "y\n")  # closes before "Create the lane folders now?"
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(repo, "log", "-1", "--format=%s").strip() == "Add parallanes"
    assert "nothing committed" not in result.stdout
    steps = result.stdout.split("Next:")[1]
    assert "Run `sh .claude/kit/parallanes lanes create`" in steps and "Once the kit's files" not in steps


def test_a_failed_commit_leaves_nothing_staged(tmp_path):
    repo = project(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    result = setup(repo, stdin="\n" * 5 + "y\n" + "n\n" + "y\n" + "y\n")  # no kit pre-commit: the owner's runs
    assert result.returncode == 0, result.stdout + result.stderr
    assert "The commit failed" in result.stderr
    assert git(repo, "diff", "--cached", "--name-only").strip() == ""


def test_a_declined_guess_isnt_asked_again_on_a_plain_rerun(tmp_path):
    repo = project(tmp_path)
    assert setup(repo, stdin=FIRST + "n\n" + "n\n").returncode == 0
    again = setup(repo, stdin="")
    assert again.returncode == 0, again.stdout + again.stderr
    assert ADD not in again.stdout
    assert "lanes suggest" in again.stdout.split("Next:")[1]


def test_an_install_from_before_profiles_keeps_both_lane_hooks(tmp_path):
    import json

    repo = project(tmp_path)
    assert setup(repo, "--yes", "--profile", "lanes").returncode == 0
    manifest = repo / ".claude" / "kit" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    del data["values"]["profile"]
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    before = (repo / ".claude" / "settings.json").read_bytes()

    result = setup(repo, "--yes")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo / ".claude" / "settings.json").read_bytes() == before
    assert "is removed" not in result.stdout
