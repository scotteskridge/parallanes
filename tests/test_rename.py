"""The rename to `parallanes` (plan 12, decisions 108-109): what people type and see, nothing else.

The command is `sh .claude/kit/parallanes`, the name the v0.2 plugin will put on the PATH. The
`.claude/kit/` folder, `kit.toml`, `kitlib`, the `KIT_*` variables and the PR label keep their
names. A project installed before the rename keeps working: the installer never deletes a file, so
its old launcher and the files that call it stay as they were.
"""

import re
import shutil
import subprocess
import sys

import pytest

from helpers import ROOT
from installer import blocks, values
from test_installer import new_repo, setup

LAUNCHERS = ROOT / "payload" / "kit-owned" / ".claude" / "kit"
OLD_NAMES = re.compile(r"\.claude/kit/kit\b|claude-code-lanes-starter")  # \b: not .claude/kit/kitlib
needs_sh = pytest.mark.skipif(shutil.which("sh") is None, reason="needs sh (Git Bash on Windows)")


def test_the_launcher_is_named_parallanes():
    assert (LAUNCHERS / "parallanes").is_file()
    assert not (LAUNCHERS / "kit").exists()


def test_the_command_is_parallanes():
    assert values.KIT_COMMAND == "sh .claude/kit/parallanes"


def test_an_earlier_installs_command_doesnt_win():
    """kit_command isn't an answer: it says how to run the kit being installed, so a re-run's newly
    rendered files call the launcher that exists."""
    found = values.detect(ROOT / "tests", {"kit_command": "sh .claude/kit/kit"})
    assert found["kit_command"] == "sh .claude/kit/parallanes"


def test_the_cli_calls_itself_parallanes():
    cli = LAUNCHERS / "cli.py"
    usage = subprocess.run([sys.executable, str(cli), "--help"], capture_output=True, text=True)
    assert usage.stdout.startswith("usage: parallanes"), usage.stdout
    refused = subprocess.run(
        [sys.executable, str(cli), "check", "rules", "--lane", "x"], capture_output=True, text=True
    )
    assert refused.returncode == 2
    assert refused.stderr.startswith("parallanes: "), refused.stderr


def test_a_block_with_the_old_markers_is_renamed_in_place():
    old = (
        "node_modules/\n"
        "# >>> claude-code-lanes-starter (managed: the installer rewrites the lines between these markers)\n"
        ".env\n"
        "# <<< claude-code-lanes-starter\n"
        "dist/\n"
    )
    merged = blocks.merge(old, ".env\n.claude/settings.local.json\n")
    assert "claude-code-lanes-starter" not in merged
    assert merged.count(blocks.BEGIN) == 1 and merged.count(blocks.END) == 1
    assert merged.startswith("node_modules/\n") and merged.endswith("dist/\n")
    assert blocks.inside(old) == [".env"]


def test_markers_with_one_old_and_one_new_name_are_broken():
    mixed = f"# >>> claude-code-lanes-starter (managed)\n.env\n{blocks.END}\n"
    with pytest.raises(blocks.BlockError):
        blocks.merge(mixed, ".env\n")


@pytest.mark.slow
def test_no_installed_file_names_the_old_command_or_repo(tmp_path):
    repo = new_repo(tmp_path)
    setup(repo)
    for path in repo.rglob("*"):
        if path.is_file() and ".git" not in path.relative_to(repo).parts:
            text = path.read_bytes().decode("utf-8", errors="replace")
            old = OLD_NAMES.search(text)
            assert old is None, f"{path.relative_to(repo).as_posix()} mentions {old.group(0)}"
    assert (repo / ".claude" / "kit" / "parallanes").is_file()
    assert not (repo / ".claude" / "kit" / "kit").exists()


@pytest.mark.slow
@needs_sh
def test_a_project_installed_before_the_rename_keeps_working(tmp_path):
    """Its own files call `sh .claude/kit/kit`: the re-run leaves that launcher, says it's the old
    name, and the new one works too."""
    repo = new_repo(tmp_path)
    setup(repo)
    kit = repo / ".claude" / "kit"
    old = kit / "kit"
    shutil.copyfile(kit / "parallanes", old)  # what a v0.1.0.dev0 install left
    agents = repo / "AGENTS.md"
    agents.write_bytes(agents.read_bytes() + b"\nRun `sh .claude/kit/kit next`.\n")

    again = setup(repo)
    assert old.is_file()
    assert ".claude/kit/kit is the old name of .claude/kit/parallanes" in again.stdout
    assert b"sh .claude/kit/kit next" in agents.read_bytes()
    for launcher in ("kit", "parallanes"):
        result = subprocess.run(
            ["sh", f".claude/kit/{launcher}", "next", "--offline"], cwd=repo, capture_output=True, text=True
        )
        assert result.returncode == 0, (launcher, result.stderr)
