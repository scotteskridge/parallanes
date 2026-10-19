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
