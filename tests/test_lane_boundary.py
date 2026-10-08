"""The lane-boundary check (decision 96): a lane's change lands only in its own and the shared paths.

The rules run in-process on path lists (fast set); the CLI and pre-commit cases use real repos (slow).
Test cases ported from lanekeeper's gate-hole tests (docs/survey-lanekeeper.md).
"""

import os
import subprocess
from types import SimpleNamespace

import pytest

from helpers import git, run_cli, write
from kitlib import commands, lane_boundary, lane_owners
from kitlib.config import Lane, LaneSettings
from lane_helpers import commit, lanes_repo

CORE = Lane(name="core", owns=["src/core/**", "tests/core/**"], scope="", resources={})
API = Lane(name="api", owns=["src/api/**"], scope="", resources={})
EVERYTHING = Lane(name="all", owns=["**"], scope="", resources={})


def config(*lanes):
    return SimpleNamespace(lanes=list(lanes or (CORE, API)), lane_settings=LaneSettings())


def flagged(lane, paths, cfg=None):
    return {finding.path: finding.message for finding in lane_boundary.check(cfg or config(), lane, paths)}


# ---- the rules ------------------------------------------------------------------------------------


def test_own_and_shared_paths_pass():
    assert flagged(CORE, ["src/core/a.py", "tests/core/test_a.py", "docs/backlog/idea.md"]) == {}


def test_another_lanes_path_fails_and_names_that_lane():
    found = flagged(CORE, ["src/core/a.py", "src/api/b.py"])
    assert list(found) == ["src/api/b.py"]
    assert "lane 'api'" in found["src/api/b.py"] and "outside lane 'core'" in found["src/api/b.py"]


def test_a_path_no_lane_owns_fails():
    found = flagged(CORE, ["README.md"])
    assert "no lane owns it" in found["README.md"]


def test_each_finding_ends_with_its_fix_and_the_advice_says_how_kit_toml_lands():
    # Backlog ownership-fix-hint (trial F8, F11): the owner shouldn't have to work out the edit.
    found = flagged(CORE, ["data dir/.gitignore", "src/api/b.py"])
    findings = lane_boundary.check(config(), CORE, ["data dir/.gitignore", "src/api/b.py"])
    found = {finding.path: finding.message for finding in findings}
    assert found["data dir/.gitignore"].endswith(
        "; add \"data dir/.gitignore\" to lane 'core''s owns in .claude/kit.toml"
    )
    assert found["src/api/b.py"].endswith("; make this change from that lane instead")
    assert lane_owners.HOW_POLICY_LANDS in lane_boundary.advice(findings)


def test_the_advice_mentions_widening_only_when_a_finding_offers_it():
    # Review round 1: a stop that never offers to widen shouldn't end with how to widen.
    advice = lane_boundary.advice(lane_boundary.check(config(), CORE, ["src/api/b.py", ".claude/kit.toml"]))
    assert "KIT_ALLOW_CROSS_LANE" in advice and lane_owners.HOW_POLICY_LANDS not in advice


def test_the_lane_policy_itself_offers_no_widening():
    assert flagged(CORE, [".claude/kit.toml"]) == {
        ".claude/kit.toml": "outside lane 'core': the lane policy belongs to no lane"
    }


def test_a_file_a_more_specific_lane_owns_fails_for_the_wider_lane():
    # Decision 97: `**` claims src/core/a.py too, but core's src/core/** is more specific.
    found = flagged(EVERYTHING, ["src/core/a.py", "README.md"], config(EVERYTHING, CORE))
    assert list(found) == ["src/core/a.py"]
    assert "** matches it, but lane 'core' owns it: src/core/** is more specific" in found["src/core/a.py"]
    assert flagged(CORE, ["src/core/a.py"], config(EVERYTHING, CORE)) == {}


def test_a_tie_fails_for_both_lanes():
    a = Lane(name="a", owns=["src/*.py"], scope="", resources={})
    b = Lane(name="b", owns=["src/a.p*"], scope="", resources={})
    for lane in (a, b):
        assert "claim it equally" in flagged(lane, ["src/a.py"], config(a, b))["src/a.py"]


def test_the_lane_policy_belongs_to_no_lane_even_one_that_owns_everything():
    # lanekeeper: widening the policy inside a lane's own change is a violation, even for `**`.
    found = flagged(EVERYTHING, [".claude/kit.toml", "src/anything.py"], config(EVERYTHING))
    assert list(found) == [".claude/kit.toml"]


def test_the_advice_is_given_once_not_per_file():
    found = flagged(CORE, ["src/api/b.py", "src/api/c.py"])
    assert all(lane_boundary.ALLOW_VARIABLE not in message for message in found.values())
    assert lane_boundary.ALLOW_VARIABLE in lane_boundary.ADVICE and "isn't a lane's" in lane_boundary.ADVICE


@pytest.mark.skipif(os.name != "nt", reason="the Windows file system ignores case, so ownership does too")
def test_case_is_ignored_on_windows():
    assert flagged(CORE, ["SRC/Core/A.py"]) == {}
    assert ".CLAUDE/Kit.toml" in flagged(EVERYTHING, [".CLAUDE/Kit.toml"], config(EVERYTHING))


@pytest.mark.parametrize(
    "branch, lane",
    [("core/fix-login", "core"), ("api/x/y", "api"), ("chore/tidy", None), ("core", None), (None, None)],
)
def test_the_lane_comes_from_a_lane_task_branch(branch, lane):
    found = lane_boundary.lane_for_branch(config(), branch)
    assert (found.name if found else None) == lane


@pytest.mark.parametrize(
    "text, shell",
    [
        ("KIT_ALLOW_CROSS_LANE=1 git commit -m x", "bash"),
        ("export KIT_ALLOW_CROSS_LANE=1", "bash"),
        ("$env:KIT_ALLOW_CROSS_LANE = '1'", "powershell"),
        ("setx KIT_ALLOW_CROSS_LANE 1", "powershell"),
        ("Set-Item env:KIT_ALLOW_CROSS_LANE 1", "powershell"),
        ("[Environment]::SetEnvironmentVariable('KIT_ALLOW_CROSS_LANE', '1')", "powershell"),
        ("echo ${KIT_ALLOW_CROSS_LANE:=1}", "bash"),
    ],
)
def test_an_agent_setting_the_override_is_caught(text, shell):
    assert commands.disables_checks(text, shell)


def test_quoting_the_override_is_not_setting_it():
    assert commands.disables_checks('git commit -m "land it with KIT_ALLOW_CROSS_LANE=1"', "bash") is None


# ---- the CLI on real repos -------------------------------------------------------------------------


def on_branch(repo, branch="core/task"):
    git(repo, "switch", "-q", "-c", branch)


def check(repo, *args, env=None):
    return run_cli(repo, "check", "lanes", *args, env=env)


@pytest.mark.slow
def test_diff_fails_on_another_lanes_file_and_names_it(tmp_path):
    repo = lanes_repo(tmp_path)
    on_branch(repo)
    commit(repo, "src/core/b.py", "y = 1\n")
    commit(repo, "src/api/c.py", "z = 1\n")
    result = check(repo, "--diff", "origin/main")
    assert result.returncode == 1, result.stderr
    assert "src/api/c.py:" in result.stdout and "lane 'api'" in result.stdout
    assert "src/core/b.py" not in result.stdout


@pytest.mark.slow
def test_a_move_counts_for_both_paths(tmp_path):
    repo = lanes_repo(tmp_path)
    commit(repo, "src/api/old.py", "x = 1\n")
    git(repo, "push", "-q", "origin", "main")
    on_branch(repo)
    git(repo, "mv", "src/api/old.py", "src/core/new.py")
    git(repo, "commit", "-q", "-m", "move")
    result = check(repo, "--diff", "origin/main")
    assert result.returncode == 1
    assert "src/api/old.py:" in result.stdout and "src/core/new.py" not in result.stdout


@pytest.mark.slow
def test_a_deletion_of_another_lanes_file_fails(tmp_path):
    repo = lanes_repo(tmp_path)
    commit(repo, "src/api/gone.py", "x = 1\n")
    git(repo, "push", "-q", "origin", "main")
    on_branch(repo)
    git(repo, "rm", "-q", "src/api/gone.py")
    git(repo, "commit", "-q", "-m", "delete")
    assert "src/api/gone.py:" in check(repo, "--diff", "origin/main").stdout


@pytest.mark.slow
def test_shared_paths_and_odd_names_pass(tmp_path):
    repo = lanes_repo(tmp_path)
    on_branch(repo)
    commit(repo, "docs/backlog/an idea.md", "# idea\n")
    commit(repo, "src/core/naïve module.py", "x = 1\n")
    result = check(repo, "--diff", "origin/main")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.slow
def test_a_missing_base_is_an_error_not_a_clean_result(tmp_path):
    repo = lanes_repo(tmp_path)
    on_branch(repo)
    commit(repo, "src/api/c.py", "z = 1\n")
    result = check(repo, "--diff", "origin/no-such-branch")
    assert result.returncode == 2
    assert "parallanes:" in result.stderr


@pytest.mark.slow
def test_a_branch_that_isnt_a_lanes_is_not_judged(tmp_path):
    repo = lanes_repo(tmp_path)
    on_branch(repo, "chore/tidy")
    commit(repo, "src/api/c.py", "z = 1\n")
    assert check(repo, "--diff", "origin/main").returncode == 0


@pytest.mark.slow
def test_lane_flag_and_ci_branch_name_pick_the_lane(tmp_path):
    repo = lanes_repo(tmp_path)
    on_branch(repo, "chore/tidy")
    commit(repo, "src/api/c.py", "z = 1\n")
    assert check(repo, "--diff", "origin/main", "--lane", "api").returncode == 0
    assert check(repo, "--diff", "origin/main", "--lane", "core").returncode == 1
    unknown = check(repo, "--diff", "origin/main", "--lane", "nope")
    assert unknown.returncode == 2 and "nope" in unknown.stderr
    # CI checks out a pull request's merge commit detached; the branch name comes from GITHUB_HEAD_REF.
    git(repo, "switch", "-q", "--detach")
    env = {**os.environ, "GITHUB_HEAD_REF": "core/task"}
    assert check(repo, "--diff", "origin/main", env=env).returncode == 1


@pytest.mark.slow
def test_the_human_override_passes_visibly(tmp_path):
    repo = lanes_repo(tmp_path)
    on_branch(repo)
    commit(repo, "src/api/c.py", "z = 1\n")
    result = check(repo, "--diff", "origin/main", env={**os.environ, lane_boundary.ALLOW_VARIABLE: "1"})
    assert result.returncode == 0
    assert lane_boundary.ALLOW_VARIABLE in result.stderr  # skipped visibly, not silently


@pytest.mark.slow
def test_lane_flag_is_refused_by_checks_that_ignore_it(tmp_path):
    repo = lanes_repo(tmp_path)
    result = run_cli(repo, "check", "rules", "--lane", "core")
    assert result.returncode == 2 and "--lane" in result.stderr


@pytest.mark.slow
def test_an_ambiguous_branch_name_still_finds_the_lane(tmp_path):
    # A tag of the same name makes `symbolic-ref --short` print heads/core/task.
    repo = lanes_repo(tmp_path)
    on_branch(repo)
    git(repo, "tag", "core/task")
    commit(repo, "src/api/c.py", "z = 1\n")
    assert check(repo, "--diff", "origin/main").returncode == 1


@pytest.mark.slow
@pytest.mark.parametrize("edit", ['name = "core"', "[[lanes]]"])
def test_a_lane_cant_escape_by_editing_the_lanes_in_its_own_change(tmp_path, edit):
    # Judged by the lanes the change started from, not the ones it writes (review round 1).
    repo = lanes_repo(tmp_path)
    on_branch(repo)
    toml = (repo / ".claude" / "kit.toml").read_text(encoding="utf-8")
    renamed = toml.replace('name = "core"', 'name = "core2"') if edit.startswith("name") else toml.split("[[lanes]]")[0]
    write(repo, ".claude/kit.toml", renamed)
    write(repo, "src/api/c.py", "z = 1\n")
    git(repo, "add", "-A")
    staged = check(repo, "--staged")  # the pre-commit hook judges by HEAD's lanes
    assert staged.returncode == 1, staged.stderr
    assert ".claude/kit.toml:" in staged.stdout and "src/api/c.py:" in staged.stdout
    git(repo, "commit", "-q", "-m", "escape")  # no hook installed here: CI and finish are next
    result = check(repo, "--diff", "origin/main")  # judged by the base's lanes
    assert result.returncode == 1, result.stderr
    assert ".claude/kit.toml:" in result.stdout and "src/api/c.py:" in result.stdout


@pytest.mark.slow
def test_a_merge_commit_is_judged_on_its_resolution_not_on_what_main_brought(tmp_path):
    # `lanes sync` on a pushed branch merges and asks for `git merge --continue`, which runs the
    # pre-commit hook: another lane's files that already landed must not block it (review round 1).
    repo = lanes_repo(tmp_path)
    commit(repo, "src/core/a.py", "x = 'main'\n")
    commit(repo, "src/api/landed.py", "y = 1\n")
    on_branch(repo, "core/task")
    git(repo, "reset", "-q", "--hard", "HEAD~2")
    commit(repo, "src/core/a.py", "x = 'lane'\n")
    merge = subprocess.run(["git", "merge", "-q", "main"], cwd=repo, capture_output=True, text=True)
    assert merge.returncode != 0  # the conflict in src/core/a.py
    write(repo, "src/core/a.py", "x = 'both'\n")
    git(repo, "add", "src/core/a.py")
    result = check(repo, "--staged")
    assert result.returncode == 0, result.stdout + result.stderr
    write(repo, "src/api/sneaked.py", "s = 1\n")  # slipped into the merge commit: still the lane's change
    git(repo, "add", "src/api/sneaked.py")
    assert "src/api/sneaked.py:" in check(repo, "--staged").stdout


@pytest.mark.slow
def test_a_commit_that_repairs_an_old_kit_toml_can_land(tmp_path):
    # Review round 2: the base's kit.toml is read only for its lanes, not checked like the current one,
    # so a rule the current kit rejects at HEAD doesn't block the commit that fixes it.
    from lane_helpers import LANES_TOML

    broken = LANES_TOML + '\n[protected]\nsecrets = [".env", "!config/.env.example"]\n'
    from helpers import sync_settings

    repo = lanes_repo(tmp_path, config=broken)
    write(repo, ".claude/kit.toml", LANES_TOML)
    sync_settings(repo)  # as the owner would after editing kit.toml, so `check settings` is clean
    git(repo, "add", "-A")
    result = run_cli(repo, "check", "all", "--staged")  # on main: not a lane branch
    assert result.returncode == 0, result.stdout + result.stderr
    on_branch(repo)  # a lane branch reads the old lanes, which are fine; kit.toml is still the lane's change
    assert ".claude/kit.toml:" in check(repo, "--staged").stdout


@pytest.mark.slow
def test_a_base_whose_lanes_dont_load_is_an_error_naming_the_commit(tmp_path):
    from lane_helpers import LANES_TOML

    repo = lanes_repo(tmp_path, config=LANES_TOML.replace('owns = ["src/api/**"]', "owns = []"))
    write(repo, ".claude/kit.toml", LANES_TOML)
    on_branch(repo)
    git(repo, "add", ".claude/kit.toml")
    result = check(repo, "--staged")
    assert result.returncode == 2
    assert "at HEAD" in result.stderr or "at commit" in result.stderr


@pytest.mark.slow
@pytest.mark.parametrize(
    "base_project",
    ["integration_branch = 1\n", 'shared_paths = "src/**"\n'],
)
def test_bad_lane_settings_at_the_base_fail_closed_with_a_message(tmp_path, base_project):
    # Review round 3: lanes_only type-checks the lane keys, so these are a ConfigError, not a traceback.
    from lane_helpers import LANES_TOML

    bad = LANES_TOML.replace('integration_branch = "main"\n', base_project)
    repo = lanes_repo(tmp_path)
    git(repo, "update-index", "--cacheinfo", "100644", _blob(repo, bad), ".claude/kit.toml")
    git(repo, "commit", "-q", "-m", "a kit.toml written around the kit")
    git(repo, "checkout", "-q", "--", ".claude/kit.toml")
    on_branch(repo)
    write(repo, ".claude/kit.toml", LANES_TOML)
    git(repo, "add", ".claude/kit.toml")
    result = check(repo, "--staged")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Traceback" not in result.stderr and "at HEAD" in result.stderr


@pytest.mark.slow
def test_a_slash_branch_that_isnt_a_lane_never_validates_the_base(tmp_path):
    # Review round 3: `chore/x` must not depend on the base's lanes loading, as `main` doesn't.
    from lane_helpers import LANES_TOML

    repo = lanes_repo(tmp_path, config=LANES_TOML.replace('owns = ["src/api/**"]', "owns = []"))
    on_branch(repo, "chore/fix-kit-toml")
    write(repo, ".claude/kit.toml", LANES_TOML)
    git(repo, "add", ".claude/kit.toml")
    result = check(repo, "--staged")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.slow
def test_named_files_outside_a_git_repo_still_check(tmp_path):
    # The kit runs in a folder that isn't a git repo (find_root falls back to kit.toml): no branch, no lane.
    from lane_helpers import LANES_TOML

    folder = tmp_path / "no git"
    write(folder, ".claude/kit.toml", LANES_TOML)
    write(folder, "src/api/c.py", "z = 1\n")
    result = check(folder, "src/api/c.py")
    assert result.returncode == 0, result.stdout + result.stderr


def _blob(repo, text):
    return subprocess.run(
        ["git", "hash-object", "-w", "--stdin"], cwd=repo, input=text, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.mark.slow
def test_named_files_are_judged_by_heads_lanes(tmp_path):
    repo = lanes_repo(tmp_path)
    on_branch(repo)
    write(repo, "src/api/c.py", "z = 1\n")
    write(repo, "src/core/d.py", "z = 1\n")
    result = check(repo, "src/api/c.py", "src/core/d.py")
    assert result.returncode == 1 and "src/api/c.py:" in result.stdout and "src/core/d.py" not in result.stdout


@pytest.mark.slow
def test_the_first_commit_of_a_new_project_is_checked(tmp_path):
    from helpers import make_repo
    from lane_helpers import LANES_TOML

    repo = make_repo(tmp_path, config=LANES_TOML)
    git(repo, "switch", "-q", "-c", "core/first")  # unborn: no commit yet
    write(repo, "src/api/c.py", "z = 1\n")
    git(repo, "add", "src/api/c.py")
    result = check(repo, "--staged")
    assert result.returncode == 1 and "src/api/c.py:" in result.stdout


@pytest.mark.slow
def test_staged_changes_are_checked_for_the_pre_commit_hook(tmp_path):
    repo = lanes_repo(tmp_path)
    on_branch(repo)
    write(repo, "src/api/c.py", "z = 1\n")
    git(repo, "add", "src/api/c.py")
    result = run_cli(repo, "check", "all", "--staged")
    assert result.returncode == 1 and "src/api/c.py:" in result.stdout
