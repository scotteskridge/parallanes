"""The CI template an installed project gets (plan 09, decision 104), and `kit test`, which it runs.

The workflow is parsed as YAML, and its check step's script is run with sh (Git's on Windows; the
runner uses bash) in a scratch repo with the variables GitHub Actions sets, so the tests exercise
what CI would do, not its text.
"""

import os
import shutil
import subprocess
import sys

import pytest
import yaml

from helpers import CLI, RULES_TOML, git, make_repo, run_cli, write
from kitlib import commands
from kitlib.config import DEFAULT_COMMANDS
from kitlib.render import render
from test_templates import read, registry

KIT = CLI.parent
LABEL = "kit:protected-change"
PROTECTED_TOML = RULES_TOML + '\n[protected]\npaths = ["vendor/**"]\n'


def workflow() -> dict:
    entries = registry()
    values = {name: entry["example"] for name, entry in entries.items()}
    return yaml.safe_load(render(read(".github/workflows/kit.yml"), values, set(entries)))


def triggers(flow: dict) -> dict:
    return flow[True]  # YAML 1.1 reads the bare key `on` as true


def check_step(flow: dict) -> dict:
    (step,) = [s for s in flow["jobs"]["kit-checks"]["steps"] if "check all" in s.get("run", "")]
    return step


# ---- the workflow's shape -----------------------------------------------------------------------


def test_runs_on_pushes_to_the_integration_branch_and_on_every_pr_label_change():
    on = triggers(workflow())
    assert on["push"]["branches"] == [registry()["integration_branch"]["example"]]
    # labeled/unlabeled: adding or removing the override label must re-run the checks.
    assert set(on["pull_request"]["types"]) == {"opened", "synchronize", "reopened", "labeled", "unlabeled"}


def test_has_the_two_jobs_with_timeouts():
    jobs = workflow()["jobs"]
    assert set(jobs) == {"kit-checks", "tests"}
    assert all(job["timeout-minutes"] for job in jobs.values())  # a hang must not hold a runner for 6 hours


def test_kit_checks_fetches_the_whole_history():
    checkout = workflow()["jobs"]["kit-checks"]["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["fetch-depth"] == 0  # `--diff origin/<base>` needs the base's commits


def test_the_override_comes_only_from_the_label_and_only_on_the_check_step():
    flow = workflow()
    step = check_step(flow)
    assert step["env"] == {
        "KIT_ALLOW_PROTECTED": f"${{{{ contains(github.event.pull_request.labels.*.name, '{LABEL}') && '1' || '' }}}}"
    }
    others = [s for job in flow["jobs"].values() for s in job["steps"] if s is not step]
    assert not any("env" in s for s in others)
    assert "KIT_ALLOW_CROSS_LANE" not in read(".github/workflows/kit.yml")  # decision 104: no lane override


def test_the_tests_job_runs_the_configured_command_after_a_marked_setup_step():
    text = read(".github/workflows/kit.yml")
    assert "Set up your stack here" in text
    steps = workflow()["jobs"]["tests"]["steps"]
    assert steps[-1]["run"] == "python .claude/kit/cli.py test"  # kit.toml's test_command, never a copy


def test_concurrency_never_cancels_a_push_run():
    # Decision 95, as in the kit's own tests.yml: a shared group on main drops pending runs.
    concurrency = workflow()["concurrency"]
    assert "github.run_id" in concurrency["group"]
    assert concurrency["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}"


# ---- the check step's script, run as CI would run it -------------------------------------------


@pytest.fixture
def project(tmp_path):
    """A repo with origin/main, and a PR branch that touches a protected path."""
    if shutil.which("sh") is None:
        pytest.skip("sh is needed to run the workflow's script (Git Bash on Windows)")
    repo = make_repo(tmp_path, config=PROTECTED_TOML)
    shutil.copytree(KIT, repo / ".claude" / "kit", ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
    write(repo, "src/app.py", "x = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "checkout", "-qb", "fix/vendor")
    write(repo, "vendor/lib.py", "y = 2\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "touch vendor")
    git(repo, "checkout", "-q", "--detach")  # as actions/checkout leaves a PR
    return repo


def run_step(repo, event, allow=""):
    script = check_step(workflow())["run"]
    # The runner's `python` is setup-python's; here it is the test's interpreter (on Windows, a bare
    # `python` may be the Store alias).
    shim = f'python() {{ "{sys.executable.replace(os.sep, "/")}" "$@"; }}\n'
    env = {
        **os.environ,
        "GITHUB_EVENT_NAME": event,
        "GITHUB_BASE_REF": "main" if event == "pull_request" else "",
        "GITHUB_HEAD_REF": "fix/vendor" if event == "pull_request" else "",
        "KIT_ALLOW_PROTECTED": allow,
    }
    return subprocess.run(["sh", "-c", shim + script], cwd=repo, env=env, capture_output=True, text=True)


@pytest.mark.slow
def test_a_pr_that_changes_a_protected_path_fails(project):
    result = run_step(project, "pull_request")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "vendor/lib.py" in result.stdout


@pytest.mark.slow
def test_the_label_lets_the_protected_change_through(project):
    result = run_step(project, "pull_request", allow="1")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.slow
def test_a_push_checks_the_whole_project_not_a_change(project):
    # After the merge, the reviewed protected change mustn't turn the integration branch red; the
    # rules still apply to every tracked file.
    assert run_step(project, "push").returncode == 0
    write(project, "src/app.py", "print(1)\n")
    git(project, "commit", "-qam", "a print")
    result = run_step(project, "push")
    assert result.returncode == 1
    assert "src/app.py:1" in result.stdout


# ---- kit test -------------------------------------------------------------------------------------


def config_with(test_command: str) -> str:
    return RULES_TOML.replace('test_command = "python -m pytest -q"', f"test_command = {test_command!r}")


def test_kit_test_runs_the_configured_command_from_the_root(tmp_path):
    repo = make_repo(tmp_path, config=config_with('python -c "import pathlib; print(pathlib.Path.cwd().name)"'))
    (repo / "src").mkdir()
    result = run_cli(repo / "src", "test")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "my project" in result.stdout


def test_kit_test_reports_a_failing_suite_as_exit_1(tmp_path):
    repo = make_repo(tmp_path, config=config_with('python -c "raise SystemExit(3)"'))
    result = run_cli(repo, "test")
    assert result.returncode == 1
    assert "exit 3" in result.stderr


def test_kit_test_without_a_command_fails_and_says_where_to_set_it(tmp_path):
    # A green CI run that tested nothing would be a false claim (decision 104).
    repo = make_repo(tmp_path, config=config_with(""))
    result = run_cli(repo, "test")
    assert result.returncode == 2
    assert "test_command" in result.stderr and ".claude/kit.toml" in result.stderr


# ---- an agent can't put the label on --------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        f"gh pr edit 12 --add-label {LABEL}",
        f"gh issue edit 12 --add-label {LABEL}",  # a PR is an issue to the API
        f"gh pr create --title t --label {LABEL}",
        f"gh pr create -l {LABEL}",
        f"gh label edit other --name {LABEL}",
    ],
)
def test_the_default_commands_block_labelling(command):
    assert commands.find_protected(command, "bash", DEFAULT_COMMANDS)


@pytest.mark.parametrize(
    "command", ["gh pr view 12", "gh pr create --title t", "gh label list", "gh pr edit 12 --title t"]
)
def test_the_default_commands_leave_ordinary_gh_alone(command):
    assert not commands.find_protected(command, "bash", DEFAULT_COMMANDS)


# ---- the installer --------------------------------------------------------------------------------


@pytest.mark.slow
def test_the_installer_adds_the_workflow_and_keeps_one_the_project_has(tmp_path):
    from test_installer import new_repo, setup

    fresh = new_repo(tmp_path, "fresh project")
    result = setup(fresh)
    # CI only gates merges once its jobs are required checks, which the kit can't set for you.
    assert "required" in result.stdout and "docs/ai/protected-paths.md" in result.stdout
    installed = (fresh / ".github" / "workflows" / "kit.yml").read_text(encoding="utf-8")
    assert "${{ github.workflow }}" in installed and "$\\{{" not in installed  # rendered, escapes gone
    assert "python .claude/kit/cli.py test" in installed

    owned = new_repo(tmp_path, "owned project")
    (owned / ".github" / "workflows").mkdir(parents=True)
    (owned / ".github" / "workflows" / "kit.yml").write_text("name: mine\n", encoding="utf-8")
    result = setup(owned)
    assert (owned / ".github" / "workflows" / "kit.yml").read_text(encoding="utf-8") == "name: mine\n"
    assert "kit.yml.kit-new" in result.stdout
