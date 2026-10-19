"""The installer's profiles, solo and lanes (plan 16, decision 121).

Solo leaves the two lane hooks out of settings.json; lanes keeps every hook. The answer is saved
like the others, so a re-run keeps it, and `--profile` changes it.
"""

import json
import subprocess
import sys

import pytest

from helpers import ROOT
from installer import profile

SETUP = ROOT / "kit_setup.py"
LANES = '\n[[lanes]]\nname = "api"\nscope = "HTTP layer"\nowns = ["server/**"]\n'


def setup(target, *args, stdin=None, yes=True):
    argv = [sys.executable, str(SETUP), "--target", str(target), *(["--yes"] if yes else []), *args]
    return subprocess.run(argv, capture_output=True, text=True, input=stdin)


def hooks(repo) -> str:
    return json.dumps(json.loads((repo / ".claude" / "settings.json").read_text(encoding="utf-8"))["hooks"])


def saved_profile(repo):
    manifest = json.loads((repo / ".claude" / "kit" / "manifest.json").read_text(encoding="utf-8"))
    return manifest["values"].get("profile")


def new_repo(tmp_path):
    repo = tmp_path / "my project"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    return repo


# ---- choosing the profile (in-process) --------------------------------------------------------


def test_a_first_install_with_yes_is_solo():
    assert profile.choose(None, {}, first_install=True, interactive=False) == "solo"


def test_the_flag_wins_over_a_saved_answer():
    assert profile.choose("lanes", {"profile": "solo"}, first_install=False, interactive=False) == "lanes"


def test_a_saved_answer_is_kept_on_a_rerun():
    assert profile.choose(None, {"profile": "lanes"}, first_install=False, interactive=True) == "lanes"


def test_an_install_from_before_profiles_keeps_its_lane_hooks():
    """Its manifest has answers but no profile: it was installed with every hook."""
    assert profile.choose(None, {"project_name": "x"}, first_install=False, interactive=False) == "lanes"


@pytest.mark.parametrize("typed, expected", [("", "solo"), ("n", "solo"), ("y", "lanes"), ("yes", "lanes")])
def test_the_question_defaults_to_solo(typed, expected):
    asked = []

    def read(prompt):
        asked.append(prompt)
        return typed

    assert profile.choose(None, {}, first_install=True, interactive=True, read=read) == expected
    assert asked == ["Run several agents at once, each in its own lane? [y/N]: "]


def test_hooks_off_for_each_profile():
    assert profile.hooks_off("solo") == {"lane-router", "ownership"}
    assert profile.hooks_off("lanes") == set()


def test_lanes_in_the_config_mean_the_lanes_profile():
    assert profile.effective("solo", explicit=False, has_lanes=True) == "lanes"
    assert profile.effective("solo", explicit=False, has_lanes=False) == "solo"


def test_asking_for_solo_with_lanes_in_the_config_is_an_error():
    with pytest.raises(profile.ProfileError, match=r"\[\[lanes\]\]"):
        profile.effective("solo", explicit=True, has_lanes=True)


# ---- whole installs ----------------------------------------------------------------------------


@pytest.mark.slow
def test_solo_installs_without_the_lane_hooks(tmp_path):
    repo = new_repo(tmp_path)
    result = setup(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    wired = hooks(repo)
    assert "protected" in wired and "rules-check" in wired
    assert "lane-router" not in wired and "ownership" not in wired
    assert saved_profile(repo) == "solo"
    assert "Profile: solo" in result.stdout


@pytest.mark.slow
def test_switching_to_lanes_and_back(tmp_path):
    repo = new_repo(tmp_path)
    assert setup(repo).returncode == 0

    on = setup(repo, "--profile", "lanes")
    assert on.returncode == 0, on.stdout + on.stderr
    assert "lane-router" in hooks(repo) and "ownership" in hooks(repo)
    assert "the ownership hook is added for the lanes profile" in on.stdout
    assert "isn't in .claude/settings.json" not in on.stdout  # not a hook the owner deleted
    assert saved_profile(repo) == "lanes"
    again = setup(repo)  # the saved answer holds: nothing to add or remove
    assert again.returncode == 0 and "is added" not in again.stdout and "is removed" not in again.stdout

    off = setup(repo, "--profile", "solo")
    assert off.returncode == 0, off.stdout + off.stderr
    assert "lane-router" not in hooks(repo) and "ownership" not in hooks(repo)
    assert "the ownership hook is removed for the solo profile" in off.stdout


@pytest.mark.slow
def test_lanes_written_into_kit_toml_turn_the_lane_hooks_on(tmp_path):
    repo = new_repo(tmp_path)
    assert setup(repo).returncode == 0
    toml = repo / ".claude" / "kit.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + LANES, encoding="utf-8")

    result = setup(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ownership" in hooks(repo)
    assert saved_profile(repo) == "lanes"


@pytest.mark.slow
def test_solo_asked_for_with_lanes_in_kit_toml_stops_with_nothing_written(tmp_path):
    repo = new_repo(tmp_path)
    assert setup(repo, "--profile", "lanes").returncode == 0
    toml = repo / ".claude" / "kit.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + LANES, encoding="utf-8")
    before = (repo / ".claude" / "settings.json").read_bytes()

    result = setup(repo, "--profile", "solo")
    assert result.returncode != 0
    assert "[[lanes]]" in result.stderr + result.stdout
    assert (repo / ".claude" / "settings.json").read_bytes() == before


@pytest.mark.slow
def test_lanes_created_on_a_solo_install_say_how_to_add_the_lane_hooks(tmp_path):
    """Lanes written by hand after a solo install have no ownership check until the installer runs
    again; `lanes create` says so instead of leaving it silent (plan 16)."""
    repo = new_repo(tmp_path)
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    assert setup(repo).returncode == 0
    toml = repo / ".claude" / "kit.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + LANES, encoding="utf-8")
    for args in (["config", "user.name", "t"], ["config", "user.email", "t@example.com"], ["add", "-A"]):
        subprocess.run(["git", *args], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "kit"], cwd=repo, check=True)
    cli = repo / ".claude" / "kit" / "cli.py"

    created = subprocess.run([sys.executable, str(cli), "lanes", "create"], cwd=repo, capture_output=True, text=True)
    assert created.returncode == 0, created.stdout + created.stderr
    assert "re-run the kit's installer with --profile lanes" in created.stdout

    assert setup(repo).returncode == 0  # the lanes in kit.toml switch the profile to lanes
    again = subprocess.run([sys.executable, str(cli), "lanes", "create"], cwd=repo, capture_output=True, text=True)
    assert "--profile lanes" not in again.stdout


@pytest.mark.slow
def test_the_question_is_asked_without_yes(tmp_path):
    repo = new_repo(tmp_path)
    answers = "\n" * 5 + "y\n" + "n\n"  # five values, lanes, no pre-commit check
    result = setup(repo, stdin=answers, yes=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Run several agents at once" in result.stdout
    assert saved_profile(repo) == "lanes"
