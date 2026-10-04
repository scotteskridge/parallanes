"""Protected paths: the shared path logic and `kit check protected` (pre-commit and CI)."""
import os

import pytest

from helpers import RULES_TOML, git, make_repo, run_cli, write
from kitlib.config import Protected
from kitlib.protected import path_reason
from test_precommit import commit, install_hook

PROTECTED_TOML = RULES_TOML + """
[protected]
paths = ["vendor/**", "docs/originals/", "*.lock"]
"""


@pytest.mark.parametrize(
    "path",
    ["vendor/lib.py", "vendor/deep/x.c", "vendor", "vendor/", "vendor\\lib.py", "docs/originals/a.md",
     "poetry.lock", "sub/poetry.lock", ".env", "app/.env.local", "x/.env.test.local"],
)
def test_protected_and_secret_paths_are_reported(path):
    protected = Protected(paths=["vendor/**", "docs/originals/", "*.lock"])
    assert path_reason(protected, path, bypass=False)


@pytest.mark.parametrize("path", ["src/vendor.py", "src/vendor/x.py", "docs/a.md", ".env.example", "README.md"])
def test_other_paths_are_not(path):
    protected = Protected(paths=["vendor/**", "docs/originals/", "*.lock"])
    assert path_reason(protected, path, bypass=False) is None


@pytest.mark.parametrize("path", [".claude/settings.json", ".claude/kit.toml", ".claude/kit/cli.py", ".githooks/pre-commit"])
def test_kit_config_is_guarded_only_in_bypass_mode(path):
    # Decision 30: ask rules cover the other modes; nobody answers an ask in bypass mode.
    assert path_reason(Protected(), path, bypass=False) is None
    assert "bypass" in path_reason(Protected(), path, bypass=True)
    assert path_reason(Protected(guard_kit=False), path, bypass=True) is None


def test_reason_names_the_pattern_and_where_it_lives():
    reason = path_reason(Protected(paths=["vendor/**"]), "vendor/a", bypass=False)
    assert "vendor/**" in reason and "[protected]" in reason


# ---- kit check protected ------------------------------------------------------------------------

def committed_repo(tmp_path):
    repo = make_repo(tmp_path, config=PROTECTED_TOML)
    write(repo, "vendor/lib.py", "x = 1\n")
    write(repo, "src/app.py", "x = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return repo


def check(repo, *args, allow=False):
    env_before = os.environ.pop("KIT_ALLOW_PROTECTED", None)
    try:
        if allow:
            os.environ["KIT_ALLOW_PROTECTED"] = "1"
        return run_cli(repo, "check", *args)
    finally:
        os.environ.pop("KIT_ALLOW_PROTECTED", None)
        if env_before is not None:
            os.environ["KIT_ALLOW_PROTECTED"] = env_before


def test_staged_change_to_a_protected_file_is_a_finding(tmp_path):
    repo = committed_repo(tmp_path)
    write(repo, "vendor/lib.py", "x = 2\n")
    git(repo, "add", "vendor/lib.py")
    result = check(repo, "protected", "--staged")
    assert result.returncode == 1
    assert "vendor/lib.py: [protected]" in result.stdout
    assert "KIT_ALLOW_PROTECTED" in result.stdout


def test_staged_deletion_and_rename_are_findings(tmp_path):
    repo = committed_repo(tmp_path)
    git(repo, "mv", "vendor/lib.py", "src/lib.py")
    result = check(repo, "protected", "--staged")
    assert result.returncode == 1
    assert "vendor/lib.py" in result.stdout  # moving a file out of a protected folder changes it


def test_staged_secret_is_a_finding(tmp_path):
    repo = committed_repo(tmp_path)
    write(repo, "config/.env", "TOKEN=x\n")
    git(repo, "add", "config/.env")
    result = check(repo, "protected", "--staged")
    assert result.returncode == 1
    assert "config/.env" in result.stdout


def test_unprotected_changes_are_clean(tmp_path):
    repo = committed_repo(tmp_path)
    write(repo, "src/app.py", "x = 2\n")
    write(repo, ".env.example", "TOKEN=\n")
    git(repo, "add", "-A")
    result = check(repo, "protected", "--staged")
    assert result.returncode == 0, result.stdout + result.stderr


def test_diff_mode_sees_branch_changes(tmp_path):
    repo = committed_repo(tmp_path)
    git(repo, "switch", "-q", "-c", "feature")
    write(repo, "vendor/lib.py", "x = 3\n")
    git(repo, "commit", "-q", "-am", "touch vendor")
    result = check(repo, "protected", "--diff", "main")
    assert result.returncode == 1
    assert "vendor/lib.py" in result.stdout


def test_explicit_files_with_windows_separators(tmp_path):
    repo = committed_repo(tmp_path)
    result = check(repo, "protected", "vendor\\lib.py")
    assert result.returncode == 1
    assert "vendor/lib.py" in result.stdout


def test_whole_project_run_skips_protected(tmp_path):
    # With no files and no diff there is no change to judge; every vendored file isn't a finding.
    repo = committed_repo(tmp_path)
    assert check(repo, "protected").returncode == 0
    assert check(repo, "all").returncode == 0


def test_check_all_includes_protected(tmp_path):
    repo = committed_repo(tmp_path)
    write(repo, "vendor/lib.py", "x = 2\n")
    git(repo, "add", "vendor/lib.py")
    assert check(repo, "all", "--staged").returncode == 1


def test_allow_variable_lets_a_human_commit_and_says_so(tmp_path):
    repo = committed_repo(tmp_path)
    write(repo, "vendor/lib.py", "x = 2\n")
    git(repo, "add", "vendor/lib.py")
    result = check(repo, "protected", "--staged", allow=True)
    assert result.returncode == 0
    assert "KIT_ALLOW_PROTECTED" in result.stderr  # skipped visibly, not silently


def test_precommit_blocks_a_protected_change(tmp_path):
    from test_precommit import install_hook  # the same setup the pre-commit tests use

    repo = committed_repo(tmp_path)
    install_hook(repo)
    write(repo, "vendor/lib.py", "x = 2\n")
    git(repo, "add", "vendor/lib.py")
    import subprocess

    result = subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=repo, capture_output=True, text=True)
    assert result.returncode != 0
    assert "vendor/lib.py" in result.stdout + result.stderr


@pytest.mark.parametrize("path", ["src", "src/", ".", "", "src/vendor"])
def test_removing_a_folder_above_an_anchored_protected_path_is_reported(path):
    # `rm -rf src` deletes src/vendor/ too.
    assert path_reason(Protected(paths=["src/vendor/**"], secrets=[]), path, bypass=False, removes=True)


@pytest.mark.parametrize("path", ["src", "."])
def test_writing_into_a_folder_above_is_not(path):
    # `cp x .` or `touch src` doesn't touch src/vendor/.
    assert path_reason(Protected(paths=["src/vendor/**"], secrets=[]), path, bypass=False) is None


@pytest.mark.parametrize("path", ["lib", "srcx", "src/other"])
def test_removing_unrelated_folders_is_not(path):
    assert path_reason(Protected(paths=["src/vendor/**"], secrets=[]), path, bypass=False, removes=True) is None


def test_unanchored_patterns_say_nothing_about_a_folder():
    assert path_reason(Protected(paths=["*.lock"], secrets=[]), "src", bypass=False, removes=True) is None


def test_paths_compare_case_insensitively_on_windows(monkeypatch):
    from kitlib import protected as module

    rules = Protected(paths=["vendor/**"])
    monkeypatch.setattr(module, "CASE_INSENSITIVE", True)
    assert path_reason(rules, "VENDOR/a.py", bypass=False)
    assert path_reason(rules, "config/.ENV", bypass=False)
    monkeypatch.setattr(module, "CASE_INSENSITIVE", False)
    assert path_reason(rules, "VENDOR/a.py", bypass=False) is None


def test_git_bash_drive_paths_map_to_windows_drives():
    from kitlib.protected import native_path

    assert native_path("/c/Users/me/x", windows=True) == "C:/Users/me/x"
    assert native_path("/d", windows=True) == "D:/"
    assert native_path("/c/Users/me/x", windows=False) == "/c/Users/me/x"
    assert native_path("/usr/lib", windows=True) == "/usr/lib"
    assert native_path("src/a", windows=True) == "src/a"


def test_powershell_does_not_read_slash_letter_as_a_drive():
    from kitlib.protected import native_path

    assert native_path("/d/vendor", windows=True, git_bash=False) == "/d/vendor"


def test_deleting_a_folder_says_it_would_remove_protected_files():
    # Live test: "live-test is protected" misdescribed which path the pattern protects.
    reason = path_reason(Protected(paths=["live-test/protected/**"], secrets=[]), "live-test", bypass=False, removes=True)
    assert "removing live-test would delete protected files" in reason
    assert "live-test/protected/**" in reason
