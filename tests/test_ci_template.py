"""The CI template an installed project gets (plan 09, decision 105), and `worklanes test`, which it runs.

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
from lane_helpers import LANES_TOML
from test_templates import read, registry

KIT = CLI.parent
LABEL = "kit:protected-change"
LABEL_VALUE = "paths"  # what the workflow sets while the label counts: protected paths, never secrets
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
    # edited: a PR moved to another base is judged against the new one (review round 1).
    assert set(on["pull_request"]["types"]) == {"opened", "synchronize", "reopened", "edited", "labeled", "unlabeled"}


def test_has_the_two_jobs_with_timeouts():
    jobs = workflow()["jobs"]
    assert set(jobs) == {"kit-checks", "tests"}
    assert all(job["timeout-minutes"] for job in jobs.values())  # a hang must not hold a runner for 6 hours


def test_kit_checks_fetches_the_whole_history():
    checkout = workflow()["jobs"]["kit-checks"]["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["fetch-depth"] == 0  # `--diff origin/<base>` needs the base's commits


def test_the_override_comes_only_from_the_label_and_only_on_the_check_step():
    # Only the run a person starts by adding this label honours it (decision 106, review round 2):
    # any later event, a push, a reopen or another label's change, is judged without it, since the
    # label stays on the PR. Shown live in plan 09's check.
    flow = workflow()
    step = check_step(flow)
    assert step["env"] == {
        "KIT_ALLOW_PROTECTED": (
            f"${{{{ github.event.action == 'labeled' && github.event.label.name == '{LABEL}' "
            f"&& '{LABEL_VALUE}' || '' }}}}"
        )
    }
    others = [s for job in flow["jobs"].values() for s in job["steps"] if s is not step]
    assert not any("env" in s for s in others)
    assert "KIT_ALLOW_CROSS_LANE" not in read(".github/workflows/kit.yml")  # decision 105: no lane override


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


def ci_project(tmp_path, config, head, changes, base=None, deletes=()):
    """A repo checked out as actions/checkout leaves a PR: detached at a merge of head into origin/main.

    origin/main moves on after head branched off, so the merge is a real two-parent commit and the
    three-dot diff has to find the merge base, as with refs/pull/N/merge.
    """
    if shutil.which("sh") is None:
        pytest.skip("sh is needed to run the workflow's script (Git Bash on Windows)")
    repo = make_repo(tmp_path, config=config)
    shutil.copytree(KIT, repo / ".claude" / "kit", ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
    for rel, text in {"src/app.py": "x = 1\n", **(base or {})}.items():
        write(repo, rel, text)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    git(repo, "checkout", "-qb", head)
    for rel, text in changes.items():
        write(repo, rel, text)
    for rel in deletes:
        git(repo, "rm", "-q", rel)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "the PR's change")
    git(repo, "checkout", "-q", "main")
    write(repo, "README.md", "main moved on\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "main moves on")
    git(repo, "update-ref", "refs/remotes/origin/main", "main")
    git(repo, "checkout", "-q", "--detach", "main")
    git(repo, "merge", "-q", "--no-ff", "--no-edit", head)
    return repo


@pytest.fixture
def project(tmp_path):
    return ci_project(tmp_path, PROTECTED_TOML, "fix/vendor", {"vendor/lib.py": "y = 2\n"})


def run_step(repo, event, allow="", head="fix/vendor"):
    script = check_step(workflow())["run"]
    # The runner's `python` is setup-python's; here it is the test's interpreter (on Windows, a bare
    # `python` may be the Store alias).
    shim = f'python() {{ "{sys.executable.replace(os.sep, "/")}" "$@"; }}\n'
    env = {
        **os.environ,
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": event,
        "GITHUB_BASE_REF": "main" if event == "pull_request" else "",
        "GITHUB_HEAD_REF": head if event == "pull_request" else "",
        "KIT_ALLOW_PROTECTED": allow,
    }
    return subprocess.run(["sh", "-c", shim + script], cwd=repo, env=env, capture_output=True, text=True)


@pytest.mark.slow
def test_a_pr_that_changes_a_protected_path_fails_and_names_the_label(project):
    result = run_step(project, "pull_request")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "vendor/lib.py" in result.stdout
    # In CI the remedy is the label; KIT_ALLOW_PROTECTED at a terminal changes nothing there.
    assert LABEL in result.stdout and "commit it with" not in result.stdout


@pytest.mark.slow
def test_the_label_lets_the_protected_change_through(project):
    result = run_step(project, "pull_request", allow=LABEL_VALUE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "allowed" in result.stderr  # said out loud


@pytest.mark.slow
def test_the_label_never_lets_a_secret_file_through(tmp_path):
    repo = ci_project(tmp_path, PROTECTED_TOML, "fix/vendor", {"vendor/lib.py": "y = 2\n", ".env": "KEY=1\n"})
    result = run_step(repo, "pull_request", allow=LABEL_VALUE)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ".env" in result.stdout and "vendor/lib.py" not in result.stdout


def test_a_staged_secret_missing_from_the_disk_is_still_added(tmp_path):
    # Review round 3: "deleted" comes from git, not from whether the file is on disk.
    repo = make_repo(tmp_path, config=PROTECTED_TOML)
    write(repo, ".env", "KEY=1\n")
    git(repo, "add", ".env")
    (repo / ".env").unlink()
    result = run_cli(repo, "check", "protected", "--staged", env={**os.environ, "KIT_ALLOW_PROTECTED": LABEL_VALUE})
    assert result.returncode == 1, result.stdout + result.stderr
    assert ".env" in result.stdout


@pytest.mark.slow
def test_the_label_lets_a_committed_secret_be_deleted(tmp_path):
    # Review round 2: removing an accidentally committed .env is the fix, not a leak.
    repo = ci_project(tmp_path, PROTECTED_TOML, "fix/env", {}, base={".env": "KEY=1\n"}, deletes=[".env"])
    result = run_step(repo, "pull_request", head="fix/env")
    assert result.returncode == 1
    assert "Removing it is right" in result.stdout
    assert run_step(repo, "pull_request", allow=LABEL_VALUE, head="fix/env").returncode == 0


@pytest.mark.slow
def test_a_secret_under_a_protected_path_is_told_the_label_wont_help(tmp_path):
    # Review round 2: paths are checked first, but the label can't let a secret through.
    repo = ci_project(tmp_path, PROTECTED_TOML, "fix/vendor", {"vendor/.env": "KEY=1\n"})
    result = run_step(repo, "pull_request")
    assert result.returncode == 1
    assert "never lands through a pull request" in result.stdout and LABEL not in result.stdout


@pytest.mark.slow
def test_the_label_never_lets_a_lane_change_another_lanes_files(tmp_path):
    repo = ci_project(tmp_path, LANES_TOML, "core/task", {"src/core/a.py": "a = 1\n", "src/api/b.py": "b = 1\n"})
    result = run_step(repo, "pull_request", allow=LABEL_VALUE, head="core/task")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "src/api/b.py" in result.stdout and "src/core/a.py" not in result.stdout


@pytest.mark.slow
def test_a_lane_pr_within_its_paths_passes(tmp_path):
    repo = ci_project(tmp_path, LANES_TOML, "core/task", {"src/core/a.py": "a = 1\n"})
    result = run_step(repo, "pull_request", head="core/task")
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


# ---- worklanes test -------------------------------------------------------------------------------------


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
    # A green CI run that tested nothing would be a false claim (decision 105).
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
        # Review round 1: gh's repo option sits anywhere before or among the subcommand words.
        f"gh -R o/r pr edit 12 --add-label {LABEL}",
        f"gh --repo o/r pr edit 12 --add-label {LABEL}",
        f"gh --repo=o/r pr edit 12 --add-label {LABEL}",
        f"gh pr --repo o/r edit 12 --add-label {LABEL}",
        f"gh pr -Ro/r edit 12 --add-label {LABEL}",
        f"gh pr new --label {LABEL}",  # gh's own alias of `pr create`
        f"gh pr create --label={LABEL}",
        f"gh pr create -l={LABEL}",
        f"gh issue edit 12 --add-label={LABEL}",
        f"gh alias set lbl 'pr edit --add-label {LABEL}'",
        "gh pr merge 12 --admin",  # merges past red required checks
        "gh -R o/r pr merge 12 --admin --squash",
        # Review round 2: a value that looks like the repo option, a short option joined to its
        # value, and an alias file.
        f"gh pr create --title -R --label {LABEL}",
        f"gh pr create --body --repo -l {LABEL}",
        f"gh pr create -l{LABEL}",
        "gh alias import aliases.yml",
        # Review round 3: gh finds the subcommand past options, and short options cluster.
        f"gh pr --add-label {LABEL} edit 12",
        f"gh issue --add-label {LABEL} edit 12",
        f"gh -R o/r pr --add-label={LABEL} edit 12",
        f"gh pr --draft new -l {LABEL}",
        f"gh pr create -dl{LABEL}",
        f"gh pr create -wdl{LABEL}",
        # Review round 4: gh's `new` alias after an option's value.
        f"gh pr -R o/r new -l {LABEL}",
        f"gh pr --title t new -l {LABEL}",
    ],
)
def test_the_default_commands_block_labelling(command):
    assert commands.find_protected(command, "bash", DEFAULT_COMMANDS)


@pytest.mark.parametrize(
    "command",
    [
        "gh pr view 12",
        "gh pr create --title t",
        "gh label list",
        "gh label create kit:protected-change",  # creating it is harmless; putting it on a PR isn't
        "gh pr edit 12 --title t",
        "gh -R o/r pr view 12",
        "gh pr merge 12 --merge --delete-branch",
        "gh alias list",
        # Review round 3: a separate value that starts with a dash and holds a space is text.
        'gh pr create --title x --body "-lots of changes"',
        'git commit -m "-n flag removed from script"',
        "gh pr --limit 1 list",
        # Review round 4: gh's clustering stops at an option that takes a value.
        "gh pr create -t x -b y -Bdevelop",
        "gh pr create -tlogin -b y",
    ],
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
    # Review round 1: the next step mustn't send the owner to require jobs their own file lacks.
    assert "compare .github/workflows/kit.yml.kit-new" in result.stdout.lower()
