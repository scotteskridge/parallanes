"""The installer never overwrites or half-writes (decision 100): the cases review round 1 found.

Each runs `kit_setup.py` as a process, like test_installer.py, and most of them twice: a first install
and a re-run are where an owner's file was at risk.
"""

import hashlib
import json
import os
import subprocess
import sys
import tomllib

import pytest

from helpers import ROOT, git
from test_installer import KIT_OWNED, new_repo, setup, tree

pytestmark = pytest.mark.slow


def run_setup(target, *args, stdin=None):
    """Without --yes: what a person running it sees."""
    return subprocess.run(
        [sys.executable, str(ROOT / "kit_setup.py"), "--target", str(target), *args],
        input=stdin,
        capture_output=True,
        text=True,
    )


def test_an_owners_file_at_a_kit_path_survives_every_rerun(tmp_path):
    repo = new_repo(tmp_path)
    mine = repo / ".claude" / "agents" / "reviewer.md"
    mine.parent.mkdir(parents=True)
    mine.write_bytes(b"MY OWN REVIEWER\n")
    first = setup(repo)
    assert "edited since install" not in first.stdout
    for _ in range(2):
        setup(repo)
        assert mine.read_bytes() == b"MY OWN REVIEWER\n"
    assert (repo / ".claude/agents/reviewer.md.kit-new").read_bytes() == (
        KIT_OWNED / ".claude/agents/reviewer.md"
    ).read_bytes()


@pytest.mark.parametrize(
    "manifest",
    [
        b"{not json",
        b"[]",
        b'{"values": []}',
        b'{"files": {"a": 1}}',
        b'{"templates": "AGENTS.md"}',
        b'{"hooks": [{}]}',
        b'{"hooks": [{"event": "PreToolUse", "group": "x"}]}',
    ],
)
def test_a_broken_manifest_stops_with_nothing_written(tmp_path, manifest):
    repo = new_repo(tmp_path)
    setup(repo)
    path = repo / ".claude" / "kit" / "manifest.json"
    path.write_bytes(manifest)
    before = tree(repo)
    result = setup(repo, check=False)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "manifest.json" in result.stderr
    assert "Traceback" not in result.stderr
    assert tree(repo) == before


def test_an_owners_gitattributes_keeps_its_rules(tmp_path):
    """Later lines win in .gitattributes: the kit must not add `* text=auto eol=lf` after the owner's."""
    repo = new_repo(tmp_path)
    (repo / ".gitattributes").write_bytes(b"*.sln text eol=crlf\n*.dat -text\n")
    setup(repo)
    text = (repo / ".gitattributes").read_text(encoding="utf-8")
    assert text.startswith("*.sln text eol=crlf\n*.dat -text\n")
    assert "* text=auto" not in text
    assert git(repo, "check-attr", "eol", "--", "x.sln").strip().endswith("crlf")
    assert git(repo, "check-attr", "eol", "--", ".githooks/pre-commit").strip().endswith("lf")


def test_a_new_projects_gitattributes_gets_the_full_rules(tmp_path):
    repo = new_repo(tmp_path)
    setup(repo)
    assert "* text=auto eol=lf" in (repo / ".gitattributes").read_text(encoding="utf-8")
    assert setup(repo).returncode == 0
    assert "* text=auto eol=lf" in (repo / ".gitattributes").read_text(encoding="utf-8")  # stable on re-run


def test_the_owners_git_hooks_are_not_switched_off(tmp_path):
    repo = new_repo(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_bytes(b"#!/bin/sh\nexit 0\n")
    result = setup(repo)
    assert git(repo, "config", "--default", "", "core.hooksPath").strip() == ""
    assert "pre-push" in result.stdout


def test_bytecode_and_installer_leftovers_are_ignored(tmp_path):
    repo = new_repo(tmp_path)
    setup(repo)
    for path in (
        ".claude/kit/__pycache__/cli.cpython-312.pyc",
        ".claude/kit/kitlib/__pycache__/x.pyc",
        "AGENTS.md.kit-new",
    ):
        assert git(repo, "check-ignore", path).strip() == path


def test_an_existing_kit_new_file_is_never_overwritten(tmp_path):
    repo = new_repo(tmp_path)
    (repo / "AGENTS.md").write_bytes(b"# mine\n")
    (repo / "AGENTS.md.kit-new").write_bytes(b"half-merged notes\n")
    result = setup(repo)
    assert (repo / "AGENTS.md.kit-new").read_bytes() == b"half-merged notes\n"
    assert "AGENTS.md.kit-new" in result.stdout


def test_a_deleted_kit_new_file_is_not_offered_again(tmp_path):
    repo = new_repo(tmp_path)
    (repo / "AGENTS.md").write_bytes(b"# mine\n")
    setup(repo)
    (repo / "AGENTS.md.kit-new").unlink()  # reviewed and dismissed, as the next steps say
    result = setup(repo)
    assert not (repo / "AGENTS.md.kit-new").exists()
    assert "AGENTS.md.kit-new" not in result.stdout


def test_dry_run_lists_every_file_it_would_write(tmp_path):
    repo = new_repo(tmp_path)
    result = setup(repo, "--dry-run")
    for rel in (".claude/kit/python-path", ".claude/kit/manifest.json", ".claude/kit/generated-rules.json"):
        assert rel in result.stdout, rel


def test_a_target_that_is_a_file_is_refused(tmp_path):
    target = tmp_path / "a file"
    target.write_bytes(b"x")
    for args in ((), ("--dry-run",)):
        result = setup(target, *args, check=False)
        assert result.returncode == 2
        assert "not a folder" in result.stderr and "Traceback" not in result.stderr


def test_a_folder_where_a_file_goes_stops_before_writing(tmp_path):
    repo = new_repo(tmp_path)
    (repo / ".claude" / "kit" / "cli.py").mkdir(parents=True)
    before = tree(repo)
    result = setup(repo, check=False)
    assert result.returncode == 2
    assert ".claude/kit/cli.py" in result.stderr and "Traceback" not in result.stderr
    assert tree(repo) == before


def test_a_symlink_in_the_way_stops_before_writing(tmp_path):
    repo = new_repo(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    try:
        os.symlink(outside, repo / "docs", target_is_directory=True)
    except OSError:
        pytest.skip("this machine can't create symbolic links")
    result = setup(repo, check=False)
    assert result.returncode == 2
    assert "docs" in result.stderr and "link" in result.stderr
    assert list(outside.iterdir()) == []


def test_a_kit_toml_that_is_not_utf8_stops_cleanly(tmp_path):
    repo = new_repo(tmp_path)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "kit.toml").write_bytes(b'[project]\nname = "\xff"\n')
    before = tree(repo)
    result = setup(repo, check=False)
    assert result.returncode == 2 and "Traceback" not in result.stderr
    assert tree(repo) == before


def test_a_subfolder_of_a_repo_is_not_told_to_git_init(tmp_path):
    repo = new_repo(tmp_path)
    sub = repo / "services" / "api"
    sub.mkdir(parents=True)
    result = setup(sub)
    assert "git init" not in result.stdout
    assert "not the root" in result.stdout
    assert git(repo, "config", "--default", "", "core.hooksPath").strip() == ""


def test_the_kit_repo_itself_is_refused():
    result = subprocess.run(
        [sys.executable, str(ROOT / "kit_setup.py"), "--yes", "--dry-run"], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "--target" in result.stderr


def test_a_rerun_uses_the_saved_answers_without_asking(tmp_path):
    repo = new_repo(tmp_path)
    setup(repo)
    before = tree(repo)
    result = run_setup(repo, stdin="")  # nothing to read: asking would fail
    assert result.returncode == 0, result.stdout + result.stderr
    assert "earlier install" in result.stdout
    assert tree(repo) == before


def test_next_steps_follow_the_files_not_the_old_answers(tmp_path):
    repo = new_repo(tmp_path)
    first = setup(repo)
    assert "Set test_command" in first.stdout and "TODO" in first.stdout
    config = repo / ".claude" / "kit.toml"
    config.write_bytes(config.read_bytes().replace(b'test_command = ""', b'test_command = "make test"'))
    agents = repo / "AGENTS.md"
    agents.write_bytes(agents.read_bytes().replace(b"TODO:", b"Done:"))
    again = setup(repo)
    assert "Set test_command" not in again.stdout and "TODO" not in again.stdout


def test_a_bom_on_gitignore_is_kept(tmp_path):
    repo = new_repo(tmp_path)
    (repo / ".gitignore").write_bytes(b"\xef\xbb\xbfnode_modules/\n")
    setup(repo)
    assert (repo / ".gitignore").read_bytes().startswith(b"\xef\xbb\xbfnode_modules/\n")


@pytest.mark.skipif(not __import__("shutil").which("sh"), reason="needs sh (Git Bash on Windows)")
def test_the_installed_kit_runs_through_its_launcher(tmp_path):
    """As the skills and docs run it: sh .claude/kit/kit, with the recorded python-path."""
    repo = new_repo(tmp_path)
    setup(repo)
    config = repo / ".claude" / "kit.toml"
    config.write_bytes(config.read_bytes().replace(b'test_command = ""', b'test_command = "exit 0"'))
    for args in (["check", "all"], ["next", "--offline"]):
        result = subprocess.run(["sh", ".claude/kit/kit", *args], cwd=repo, capture_output=True, text=True)
        assert result.returncode == 0, (args, result.stdout, result.stderr)
    manifest = json.loads((repo / ".claude/kit/manifest.json").read_text(encoding="utf-8"))
    assert (
        manifest["files"][".claude/kit/cli.py"]
        == hashlib.sha256((KIT_OWNED / ".claude/kit/cli.py").read_bytes()).hexdigest()
    )
    assert tomllib.loads(config.read_text(encoding="utf-8"))["project"]["test_command"] == "exit 0"


# ---- review round 2 ---------------------------------------------------------------------------


def test_a_kit_new_deleted_after_the_kept_note_comes_back(tmp_path):
    """The note says "delete it to get a new one": the next run must keep that promise."""
    repo = new_repo(tmp_path)
    (repo / "AGENTS.md").write_bytes(b"# mine\n")
    (repo / "AGENTS.md.kit-new").write_bytes(b"my own notes\n")
    assert "delete it to get a new one" in setup(repo).stdout
    (repo / "AGENTS.md.kit-new").unlink()
    setup(repo)
    offered = (repo / "AGENTS.md.kit-new").read_text(encoding="utf-8")
    assert offered.startswith("# my project") and "my own notes" not in offered  # the kit's rendered AGENTS.md


def test_a_new_kit_version_is_offered_again_after_a_deletion(tmp_path):
    repo = new_repo(tmp_path)
    (repo / "AGENTS.md").write_bytes(b"# mine\n")
    setup(repo)
    (repo / "AGENTS.md.kit-new").unlink()
    manifest_path = repo / ".claude" / "kit" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["offered"]["AGENTS.md"] = "0" * 64  # as if an older kit version had been offered
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    setup(repo)
    assert (repo / "AGENTS.md.kit-new").is_file()


def test_gitattributes_keeps_the_full_block_when_the_owner_adds_a_rule(tmp_path):
    repo = new_repo(tmp_path)
    setup(repo)
    path = repo / ".gitattributes"
    path.write_bytes(path.read_bytes() + b"*.sln text eol=crlf\n")
    setup(repo)
    assert "* text=auto eol=lf" in path.read_text(encoding="utf-8")


def test_gitattributes_keeps_the_narrow_block_when_the_owner_removes_their_rules(tmp_path):
    repo = new_repo(tmp_path)
    path = repo / ".gitattributes"
    path.write_bytes(b"*.sln text eol=crlf\n")
    setup(repo)
    path.write_bytes(path.read_bytes().replace(b"*.sln text eol=crlf\n", b""))
    setup(repo)
    assert "* text=auto" not in path.read_text(encoding="utf-8")


@pytest.mark.skipif(sys.platform != "win32", reason="drive letters are Windows")
def test_a_target_on_a_missing_drive_stops_instead_of_hanging(tmp_path):
    from pathlib import Path

    letter = next(letter for letter in "QRSTUVWXYZ" if not Path(f"{letter}:/").exists())
    result = subprocess.run(
        [sys.executable, str(ROOT / "kit_setup.py"), "--target", f"{letter}:/proj", "--yes", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2
    assert "doesn't exist" in result.stderr


def test_no_precommit_answer_is_saved_when_nobody_was_asked(tmp_path):
    """Outside a repo nothing is asked, so a later run (after `git init`) must still ask."""
    folder = tmp_path / "my project"
    folder.mkdir()
    setup(folder)
    manifest = json.loads((folder / ".claude" / "kit" / "manifest.json").read_text(encoding="utf-8"))
    assert "precommit" not in manifest["values"]
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=folder, check=True)
    result = run_setup(folder, stdin="n\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(folder, "config", "--default", "", "core.hooksPath").strip() == ""
