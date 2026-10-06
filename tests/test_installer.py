"""The installer, `kit_setup.py` (plan 08, decisions 99-101): what it writes, what it never overwrites.

Most tests run it as a process with `--yes`, the way the bootstrappers do, into a folder whose path
has a space. The unit tests at the top cover the pieces that decide what happens to an existing file.
"""

import hashlib
import json
import subprocess
import sys
import tomllib

import pytest

from helpers import ROOT, git
from installer import blocks, settings_hooks, values

SETUP = ROOT / "kit_setup.py"
KIT_OWNED = ROOT / "payload" / "kit-owned"


def setup(target, *args, check=True):
    result = subprocess.run(
        [sys.executable, str(SETUP), "--target", str(target), "--yes", *args], capture_output=True, text=True
    )
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def tree(folder):
    """Every file under folder (but .git) with a hash of its bytes."""
    return {
        path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(folder).parts
    }


def new_repo(tmp_path, name="my project"):
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    return repo


# ---- managed blocks (decision 100) ------------------------------------------------------------


def test_block_is_added_after_the_owners_lines():
    merged = blocks.merge("node_modules/\n", "# kit\n.env\n")
    assert merged.startswith("node_modules/\n")
    assert f"{blocks.BEGIN}\n# kit\n.env\n{blocks.END}\n" in merged


def test_block_is_replaced_in_place_and_the_rest_is_kept():
    first = blocks.merge("a\n", "old\n") + "b\n"
    merged = blocks.merge(first, "new\n")
    assert merged == f"a\n\n{blocks.BEGIN}\nnew\n{blocks.END}\nb\n"


def test_block_merge_is_idempotent():
    once = blocks.merge("a\n", "x\n")
    assert blocks.merge(once, "x\n") == once


def test_block_keeps_crlf_files_crlf():
    merged = blocks.merge("a\r\nb\r\n", "x\n")
    assert "\r\n" in merged and "\n" not in merged.replace("\r\n", "")


@pytest.mark.parametrize(
    "text",
    [
        f"{blocks.BEGIN}\nx\n",  # lone begin
        f"x\n{blocks.END}\n",  # lone end
        f"{blocks.END}\nx\n{blocks.BEGIN}\n",  # reversed
        f"{blocks.BEGIN}\n{blocks.END}\n{blocks.BEGIN}\n{blocks.END}\n",  # doubled
    ],
)
def test_a_broken_block_is_an_error_never_repaired(text):
    with pytest.raises(blocks.BlockError):
        blocks.merge(text, "x\n")


# ---- values (decision 101) --------------------------------------------------------------------


@pytest.mark.parametrize("value", ['pytest -k "not slow"', r"C:\tools\run.bat", 'a\\"b', "tab\there"])
def test_toml_strings_round_trip(value):
    assert tomllib.loads(f"v = {values.toml_string(value)}")["v"] == value


@pytest.mark.parametrize(
    "file, content, expected",
    [
        ("pyproject.toml", "[project]\nname='x'\n", "python -m pytest"),
        ("package.json", '{"scripts": {"test": "vitest"}}', "npm test"),
        ("package.json", '{"scripts": {}}', ""),
        ("go.mod", "module x\n", "go test ./..."),
        ("Cargo.toml", "[package]\n", "cargo test"),
    ],
)
def test_test_command_is_detected(tmp_path, file, content, expected):
    (tmp_path / file).write_text(content, encoding="utf-8")
    assert values.detect(tmp_path, {})["test_command"] == expected


def test_detected_defaults_for_an_empty_folder(tmp_path):
    folder = tmp_path / "Shop Api"
    folder.mkdir()
    found = values.detect(folder, {})
    assert found["project_name"] == "Shop Api"
    assert found["integration_branch"] == "main"
    assert found["test_command"] == ""


def test_previous_answers_win_over_detection(tmp_path):
    (tmp_path / "go.mod").write_text("module x\n", encoding="utf-8")
    found = values.detect(tmp_path, {"test_command": "make test", "install_date": "2026-01-02"})
    assert found["test_command"] == "make test"
    assert found["install_date"] == "2026-01-02"


def test_questions_take_typed_answers_and_keep_defaults_on_enter():
    answers = iter(["Shop", "", "Go 1.23", "", ""])
    got = values.ask(
        {"project_name": "x", "project_description": "d", "stack": "s", "test_command": "t", "integration_branch": "b"},
        read=lambda prompt: next(answers),
    )
    assert got == {
        "project_name": "Shop",
        "project_description": "d",
        "stack": "Go 1.23",
        "test_command": "t",
        "integration_branch": "b",
    }


# ---- hook wiring in settings.json -------------------------------------------------------------


def test_hooks_are_added_once_and_owner_hooks_are_kept():
    owner = {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo mine"}]}
    settings = {"hooks": {"PreToolUse": [owner]}}
    record = settings_hooks.merge(settings, [])
    names = [
        group["hooks"][0]["command"].rsplit(" ", 1)[-1]
        for groups in settings["hooks"].values()
        for group in groups
        if group is not owner
    ]
    assert sorted(names) == ["lane-router", "ownership", "protected", "rules-check"]
    assert settings["hooks"]["PreToolUse"][0] is owner
    again = settings_hooks.merge(settings, record)
    assert again == record
    assert sum(len(groups) for groups in settings["hooks"].values()) == 5


def test_a_hook_the_kit_no_longer_writes_is_removed_but_an_owner_copy_stays():
    stale = {"matcher": "Edit", "hooks": [{"type": "command", "command": "sh old"}]}
    owner = {"matcher": "Edit", "hooks": [{"type": "command", "command": "sh mine"}]}
    settings = {"hooks": {"PostToolUse": [dict(stale), owner]}}
    settings_hooks.merge(settings, [{"event": "PostToolUse", "group": stale}])
    assert stale not in settings["hooks"]["PostToolUse"]
    assert owner in settings["hooks"]["PostToolUse"]


def test_hook_commands_use_the_launcher_and_quote_the_project_dir():
    for event, groups in settings_hooks.expected().items():
        for group in groups:
            command = group["hooks"][0]["command"]
            assert command.startswith('sh "$CLAUDE_PROJECT_DIR/.claude/kit/hook" '), (event, command)


# ---- a whole install --------------------------------------------------------------------------


@pytest.mark.slow
def test_install_into_an_existing_repo_with_spaces(tmp_path):
    repo = new_repo(tmp_path)
    (repo / "pyproject.toml").write_text("[project]\nname = 'shop'\n", encoding="utf-8")
    setup(repo)

    kit = repo / ".claude" / "kit"
    manifest = json.loads((kit / "manifest.json").read_text(encoding="utf-8"))
    for rel, digest in manifest["files"].items():
        assert hashlib.sha256((repo / rel).read_bytes()).hexdigest() == digest, rel
        assert rel == (KIT_OWNED / rel).relative_to(KIT_OWNED).as_posix()
    assert ".claude/kit/cli.py" in manifest["files"]
    assert not any("__pycache__" in rel or rel.endswith("python-path") for rel in manifest["files"])

    for rel in ("AGENTS.md", "CLAUDE.md", ".claude/kit.toml", "docs/ai/WORKFLOW.md", "docs/plans/finished/.gitkeep"):
        data = (repo / rel).read_bytes()
        assert b"\r\n" not in data, rel
        assert b"{{" not in data, rel
    config = tomllib.loads((repo / ".claude" / "kit.toml").read_text(encoding="utf-8"))
    assert config["project"]["name"] == "my project"
    assert config["project"]["test_command"] == "python -m pytest"
    assert (kit / "python-path").read_text(encoding="utf-8").strip() == sys.executable
    assert git(repo, "config", "core.hooksPath").strip() == ".githooks"
    assert git(repo, "check-ignore", ".claude/kit/python-path").strip() == ".claude/kit/python-path"

    settings = json.loads((repo / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings["permissions"]["deny"]  # the rules `kit settings sync` writes; check settings agrees
    assert set(settings["hooks"]) == {"PreToolUse", "PostToolUse", "SessionStart"}


@pytest.mark.slow
def test_the_installed_kit_runs_and_its_settings_agree(tmp_path):
    repo = new_repo(tmp_path)
    setup(repo)
    for args in (["check", "settings"], ["check", "rules"], ["next", "--offline"]):
        result = subprocess.run([sys.executable, ".claude/kit/cli.py", *args], cwd=repo, capture_output=True, text=True)
        assert result.returncode == 0, (args, result.stdout, result.stderr)


@pytest.mark.slow
def test_install_into_a_new_folder(tmp_path):
    target = tmp_path / "brand new" / "app"
    result = setup(target)
    assert (target / "AGENTS.md").is_file()
    assert "not a git repository" in result.stdout  # pre-commit skipped, and the next steps say why


@pytest.mark.slow
def test_dry_run_writes_nothing(tmp_path):
    repo = new_repo(tmp_path)
    (repo / "CLAUDE.md").write_text("# mine\n", encoding="utf-8")
    before = tree(repo)
    result = setup(repo, "--dry-run")
    assert tree(repo) == before
    assert git(repo, "config", "--default", "", "core.hooksPath").strip() == ""
    assert "create" in result.stdout and "AGENTS.md" in result.stdout
    assert "CLAUDE.md.kit-new" in result.stdout
    assert ".claude/settings.json" in result.stdout


@pytest.mark.slow
def test_existing_files_are_never_overwritten(tmp_path):
    repo = new_repo(tmp_path)
    (repo / "CLAUDE.md").write_text("# mine\n", encoding="utf-8")
    (repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    owner_hook = {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo mine"}]}
    owner = {"permissions": {"deny": ["Read(./secret.txt)"]}, "hooks": {"PreToolUse": [owner_hook]}}
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.json").write_text(json.dumps(owner, indent=4) + "\n", encoding="utf-8")

    result = setup(repo)

    assert (repo / "CLAUDE.md").read_text(encoding="utf-8") == "# mine\n"
    assert "@AGENTS.md" in (repo / "CLAUDE.md.kit-new").read_text(encoding="utf-8")
    assert "CLAUDE.md.kit-new" in result.stdout
    ignore = (repo / ".gitignore").read_text(encoding="utf-8")
    assert ignore.startswith("node_modules/\n") and blocks.BEGIN in ignore and ".claude/worktrees/" in ignore
    settings = json.loads((repo / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "Read(./secret.txt)" in settings["permissions"]["deny"]
    assert settings["hooks"]["PreToolUse"][0] == owner_hook
    assert '    "permissions"' in (repo / ".claude" / "settings.json").read_text(encoding="utf-8")  # owner's indent


@pytest.mark.slow
def test_a_broken_managed_block_stops_before_writing(tmp_path):
    repo = new_repo(tmp_path)
    (repo / ".gitignore").write_text(f"{blocks.BEGIN}\nx\n", encoding="utf-8")
    before = tree(repo)
    result = setup(repo, check=False)
    assert result.returncode == 2
    assert ".gitignore" in result.stderr
    assert tree(repo) == before


@pytest.mark.slow
def test_a_rerun_changes_nothing(tmp_path):
    repo = new_repo(tmp_path)
    setup(repo)
    before = tree(repo)
    result = setup(repo)
    assert tree(repo) == before
    planned = [line.split()[0] for line in result.stdout.splitlines() if line.startswith("  ") and line.split()]
    assert not {"create", "replace", "kit-new", "block", "settings"} & set(planned), result.stdout


@pytest.mark.slow
def test_a_rerun_keeps_edited_files(tmp_path):
    repo = new_repo(tmp_path)
    setup(repo)
    skill = repo / ".claude" / "skills" / "next" / "SKILL.md"
    skill.write_text("my edit\n", encoding="utf-8")
    agents = repo / "AGENTS.md"
    agents.write_text("# my rules\n", encoding="utf-8")

    result = setup(repo)

    assert skill.read_text(encoding="utf-8") == "my edit\n"
    assert (skill.parent / "SKILL.md.kit-new").read_bytes() == (KIT_OWNED / ".claude/skills/next/SKILL.md").read_bytes()
    assert "SKILL.md.kit-new" in result.stdout
    assert agents.read_text(encoding="utf-8") == "# my rules\n"  # project-owned: rendered once
    assert not (repo / "AGENTS.md.kit-new").exists()


@pytest.mark.slow
def test_a_rerun_replaces_an_unedited_kit_file(tmp_path):
    repo = new_repo(tmp_path)
    setup(repo)
    manifest_path = repo / ".claude" / "kit" / "manifest.json"
    skill = repo / ".claude" / "skills" / "next" / "SKILL.md"
    # As if an older kit installed it: the file matches what the manifest recorded.
    skill.write_bytes(b"old kit text\n")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][".claude/skills/next/SKILL.md"] = hashlib.sha256(b"old kit text\n").hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    setup(repo)

    assert skill.read_bytes() == (KIT_OWNED / ".claude/skills/next/SKILL.md").read_bytes()
    assert not (skill.parent / "SKILL.md.kit-new").exists()


@pytest.mark.slow
def test_quotes_in_the_test_command_still_make_a_valid_kit_toml(tmp_path):
    repo = new_repo(tmp_path)
    answers = "\n".join(["", "", "", 'pytest -k "not slow" C:\\x', "", "y"]) + "\n"
    result = subprocess.run(
        [sys.executable, str(SETUP), "--target", str(repo)], input=answers, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    config = tomllib.loads((repo / ".claude" / "kit.toml").read_text(encoding="utf-8"))
    assert config["project"]["test_command"] == 'pytest -k "not slow" C:\\x'
