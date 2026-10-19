"""The lanes guessed from a project's folders (plan 16, decision 122)."""

import tomllib

import pytest

from helpers import git, make_repo, run_cli, write
from kitlib import lane_suggest
from kitlib.config import lanes_only


def _names(paths):
    lanes, _ = lane_suggest.suggest(paths)
    return {lane.name: lane.owns for lane in lanes}


def test_top_level_code_folders_become_lanes():
    paths = ["server/app.py", "server/db/models.py", "public/index.html", "README.md"]
    assert _names(paths) == {"server": ["server/**"], "public": ["public/**"]}


def test_a_source_root_is_split_into_its_folders():
    paths = ["src/core/a.py", "src/api/b.py", "src/main.py", "pyproject.toml"]
    assert _names(paths) == {"core": ["src/core/**"], "api": ["src/api/**"]}


def test_a_single_package_under_src_is_split_one_level_down():
    paths = ["src/shop/__init__.py", "src/shop/core/a.py", "src/shop/api/b.py"]
    assert _names(paths) == {"core": ["src/shop/core/**"], "api": ["src/shop/api/**"]}


def test_matching_test_folders_go_with_their_lane():
    paths = ["src/core/a.py", "src/api/b.py", "tests/core/test_a.py", "tests/conftest.py"]
    assert _names(paths) == {"core": ["src/core/**", "tests/core/**"], "api": ["src/api/**"]}


@pytest.mark.parametrize(
    "folder", [".github", ".claude", "docs", "tests", "test", "build", "dist", "vendor", "node_modules", "_private"]
)
def test_folders_that_arent_a_lanes_code_are_skipped(folder):
    paths = ["server/a.py", "public/b.js", f"{folder}/x.txt"]
    assert set(_names(paths)) == {"server", "public"}


def test_one_code_folder_gives_no_guess_and_says_why():
    lanes, reason = lane_suggest.suggest(["src/app.py", "src/util.py", "docs/a.md"])
    assert lanes == []
    assert "one" in reason


def test_no_code_folders_gives_no_guess_and_says_why():
    lanes, reason = lane_suggest.suggest(["README.md", "docs/a.md"])
    assert lanes == []
    assert reason


def test_more_than_five_folders_gives_no_guess_and_says_why():
    paths = [f"{name}/a.py" for name in ("a1", "b2", "c3", "d4", "e5", "f6")]
    lanes, reason = lane_suggest.suggest(paths)
    assert lanes == []
    assert "6" in reason


def test_names_are_made_valid_lane_names():
    paths = ["Web_UI/a.js", "API Server/b.py"]
    assert set(_names(paths)) == {"web-ui", "api-server"}


def test_two_folders_with_the_same_name_are_told_apart():
    paths = ["apps/web/a.js", "apps/api/b.js", "packages/web/c.js", "packages/ui/d.js"]
    names = set(_names(paths))
    assert len(names) == 4
    assert {"apps-web", "packages-web"} <= names


def test_the_toml_is_valid_lanes_config():
    lanes, _ = lane_suggest.suggest(["server/a.py", "public/b.js", "tests/server/t.py"])
    text = lane_suggest.to_toml(lanes)
    parsed = tomllib.loads(text)["lanes"]
    assert [lane["name"] for lane in parsed] == ["public", "server"]  # sorted, so a re-run gives the same text
    config = lanes_only('[project]\nname = "x"\n' + text, "server")
    assert config is not None


def test_lanes_suggest_prints_the_guess_from_tracked_files(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "server/app.py", "x = 1\n")
    write(repo, "public/index.html", "<p></p>\n")
    write(repo, "untracked/a.py", "y = 1\n")
    git(repo, "add", "server", "public", ".claude")
    result = run_cli(repo, "lanes", "suggest")
    assert result.returncode == 0, result.stderr
    assert 'name = "server"' in result.stdout
    assert 'name = "public"' in result.stdout
    assert "untracked" not in result.stdout


def test_lanes_suggest_says_why_when_it_has_no_guess(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/app.py", "x = 1\n")
    git(repo, "add", "-A")
    result = run_cli(repo, "lanes", "suggest")
    assert result.returncode == 0, result.stderr
    assert "[[lanes]]" not in result.stdout
    assert "one" in result.stdout
