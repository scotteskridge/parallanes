"""`parallanes lanes create`, `status` and the lane-router on real repos: install hints (decision 103)."""

import json

import pytest

from helpers import git, run_cli, write
from kitlib import lane_deps
from lane_helpers import LANES_TOML, PACKAGE_JSON, commit, lane_dir, lanes_repo, no_gh_env

pytestmark = pytest.mark.slow  # real repos, worktrees and CLI processes: seconds a test on Windows


def node_repo(tmp_path, lockfile="package-lock.json", manifest="package.json", config=LANES_TOML):
    repo = lanes_repo(tmp_path, config=config)
    write(repo, manifest, PACKAGE_JSON)
    if lockfile:
        write(repo, lockfile, "{}\n")
    commit(repo, "README.md", "# app\n")
    git(repo, "push", "-q")
    return repo


def test_create_ends_each_new_lane_with_its_install_command(tmp_path):
    repo = node_repo(tmp_path)
    result = run_cli(repo, "lanes", "create")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    for name in ("core", "api"):
        at = next(i for i, line in enumerate(lines) if line.startswith(f"{name}: created"))
        assert lines[at + 1] == "  install in this lane: npm ci"
    # Why, once: the trial's agents never noticed (F4).
    assert result.stdout.count("parent folders") == 1
    assert "main checkout" in result.stdout


def test_create_without_a_lockfile_says_its_the_owners_call(tmp_path):
    repo = node_repo(tmp_path, lockfile=None)
    result = run_cli(repo, "lanes", "create", "core")
    assert result.returncode == 0, result.stderr
    assert "  install in this lane: the owner's call (package.json has no lockfile)" in result.stdout.splitlines()


def test_a_nested_python_lane_is_not_told_about_node(tmp_path):
    repo = node_repo(tmp_path, lockfile="uv.lock", manifest="pyproject.toml")
    result = run_cli(repo, "lanes", "create", "core")
    assert result.returncode == 0, result.stderr
    assert "  install in this lane: uv sync" in result.stdout.splitlines()
    assert lane_deps.WHY in result.stdout and "Node" not in result.stdout


def test_lanes_outside_the_main_checkout_are_not_told_about_parent_folders(tmp_path):
    config = LANES_TOML.replace(
        'integration_branch = "main"', 'integration_branch = "main"\nworktree_root = "../{project}-lanes"'
    )
    repo = node_repo(tmp_path, config=config)
    result = run_cli(repo, "lanes", "create", "core")
    assert result.returncode == 0, result.stderr
    assert "  install in this lane: npm ci" in result.stdout.splitlines()
    assert lane_deps.WHY in result.stdout and "parent folders" not in result.stdout
    folder = tmp_path / "demo-lanes" / "core"
    payload = json.dumps({"cwd": str(folder), "hook_event_name": "SessionStart", "source": "startup"})
    brief = run_cli(folder, "hook", "lane-router", stdin=payload).stdout
    assert "run `npm ci` here" in brief and "main checkout" not in brief


def test_a_lane_that_fails_later_still_gets_its_install_line(tmp_path):
    repo = node_repo(tmp_path)
    write(repo, ".worktreeinclude", ".claude/settings.local.json\n")
    write(repo, ".claude/settings.local.json", "{ not json")  # copied, then unreadable: PartialCreate
    result = run_cli(repo, "lanes", "create", "core")
    assert result.returncode == 2 and "settings.local.json" in result.stderr
    assert "  install in this lane: npm ci" in result.stdout.splitlines()
    assert lane_deps.WHY_NESTED in result.stdout


def test_create_without_a_manifest_says_nothing_about_installing(tmp_path):
    repo = lanes_repo(tmp_path)
    result = run_cli(repo, "lanes", "create")
    assert result.returncode == 0, result.stderr
    assert "install" not in result.stdout and "parent folders" not in result.stdout


def test_lanes_already_created_and_dry_runs_get_no_hint(tmp_path):
    repo = node_repo(tmp_path)
    assert "would create" in run_cli(repo, "lanes", "create", "--dry-run").stdout
    assert "install" not in run_cli(repo, "lanes", "create", "--dry-run").stdout
    assert run_cli(repo, "lanes", "create", "core").returncode == 0
    again = run_cli(repo, "lanes", "create", "core")
    assert "already created" in again.stdout and "install" not in again.stdout


def test_status_and_router_warn_until_the_lane_has_node_modules(tmp_path):
    repo = node_repo(tmp_path)
    assert run_cli(repo, "lanes", "create", "core").returncode == 0
    folder = lane_dir(repo, "core")

    def router():
        payload = json.dumps({"cwd": str(folder), "hook_event_name": "SessionStart", "source": "startup"})
        return run_cli(folder, "hook", "lane-router", stdin=payload).stdout

    status = run_cli(repo, "lanes", "status", env=no_gh_env(repo)).stdout
    core_line = next(line for line in status.splitlines() if line.startswith("core "))
    assert "no node_modules (npm ci)" in core_line
    assert "no node_modules" in router() and "npm ci" in router()

    (folder / "node_modules" / "express").mkdir(parents=True)
    assert "node_modules" not in run_cli(repo, "lanes", "status", env=no_gh_env(repo)).stdout
    assert "node_modules" not in router()
