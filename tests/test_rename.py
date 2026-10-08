"""The rename to `parallanes` (plan 12, decisions 108-109): what people type and see, nothing else.

The command is `sh .claude/kit/parallanes`, the name the v0.2 plugin will put on the PATH. The
`.claude/kit/` folder, `kit.toml`, `kitlib`, the `KIT_*` variables and the PR label keep their
names. A project installed before the rename keeps working: the installer never deletes a file, so
its old launcher and the files that call it stay as they were.
"""

import hashlib
import json
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


def old_install(repo):
    """Turn a fresh install into what the kit wrote before the rename (review round 1: copying the new
    launcher wasn't one): the old launcher, old block markers, the old command in every file, and a
    manifest whose hashes and kit_command match those files, as main's installer recorded them."""
    kit = repo / ".claude" / "kit"
    (kit / "parallanes").rename(kit / "kit")
    swaps = [
        ("# >>> parallanes", "# >>> claude-code-lanes-starter"),
        ("# <<< parallanes", "# <<< claude-code-lanes-starter"),
        (".claude/kit/parallanes", ".claude/kit/kit"),
    ]
    for path in repo.rglob("*"):
        if path.is_file() and ".git" not in path.relative_to(repo).parts:
            data = path.read_bytes()
            for new, old in swaps:
                data = data.replace(new.encode(), old.encode())
            path.write_bytes(data)
    manifest_path = kit / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = {rel: hashlib.sha256((repo / rel).read_bytes()).hexdigest() for rel in manifest["files"]}
    assert manifest["values"]["kit_command"] == "sh .claude/kit/kit"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


@pytest.mark.slow
@needs_sh
def test_a_project_installed_before_the_rename_keeps_working(tmp_path):
    repo = new_repo(tmp_path)
    (repo / ".gitattributes").write_text("*.png binary\n", encoding="utf-8")  # the owner's: narrow block
    setup(repo)
    old_install(repo)
    assert ".claude/kit/kit text eol=lf" in (repo / ".gitattributes").read_text(encoding="utf-8")

    again = setup(repo)

    kit = repo / ".claude" / "kit"
    assert (kit / "kit").is_file() and (kit / "parallanes").is_file()
    for rel in (".gitignore", ".gitattributes", ".worktreeinclude"):
        text = (repo / rel).read_text(encoding="utf-8")
        assert "claude-code-lanes-starter" not in text, rel
        assert text.count(blocks.BEGIN) == 1, rel
    # The old launcher keeps LF, or a CRLF checkout on Windows breaks it for every file still calling it.
    attributes = (repo / ".gitattributes").read_text(encoding="utf-8")
    assert ".claude/kit/kit text eol=lf" in attributes and ".claude/kit/parallanes text eol=lf" in attributes
    manifest = json.loads((kit / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["values"]["kit_command"] == "sh .claude/kit/parallanes"
    assert "parallanes" in (repo / ".claude/skills/next/SKILL.md").read_text(encoding="utf-8")  # replaced
    # The note names the files that still call the old launcher, so "delete it once none do" is doable.
    note = next(line for line in again.stdout.splitlines() if "old name" in line)
    assert "CLAUDE.md" in note and "docs/ai/parallel-lanes.md" in note
    for launcher in ("kit", "parallanes"):
        result = subprocess.run(
            ["sh", f".claude/kit/{launcher}", "next", "--offline"], cwd=repo, capture_output=True, text=True
        )
        assert result.returncode == 0, (launcher, result.stderr)


def test_an_owners_line_that_starts_like_a_marker_isnt_one():
    """Markers match whole, not by prefix: `# >>> parallanes-trial` is the owner's own line."""
    text = "# >>> parallanes-trial notes\nkeep/\n"
    merged = blocks.merge(text, ".env\n")
    assert merged.startswith(text) and merged.count(blocks.BEGIN) == 1


@pytest.mark.parametrize("gap", ["\t", " "])
def test_a_marker_followed_by_any_space_is_still_a_marker(gap):
    text = f"# >>> parallanes{gap}(managed)\n.env\n{blocks.END}\n"
    assert blocks.inside(text) == [".env"]


def test_a_bom_before_the_block_on_line_one_is_kept():
    text = "﻿" + blocks.BEGIN + "\r\nold\r\n" + blocks.END + "\r\n"
    merged = blocks.merge(text, "new\n")
    assert merged.startswith("﻿" + blocks.BEGIN) and "new\r\n" in merged
