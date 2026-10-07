"""The installer, `kit_setup.py` (plan 08, decisions 99-101): what it writes, what it never overwrites.

Each test runs it as a process with `--yes`, the way the bootstrappers do, into a folder whose path
has a space. Unit tests of its pieces are in test_installer_units.py.
"""

import hashlib
import json
import subprocess
import sys
import tomllib

import pytest

from helpers import ROOT, git
from installer import blocks

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
def test_a_rerun_honours_hooks_switched_off_and_brings_back_the_protected_hook(tmp_path):
    """Decision 102: [hooks] switches rules-check and lane-router off; the protected hook always returns."""
    repo = new_repo(tmp_path)
    setup(repo)
    toml = repo / ".claude" / "kit.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + "\n[hooks]\nrules_check = false\n", encoding="utf-8")
    path = repo / ".claude" / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8"))
    settings["hooks"]["PreToolUse"] = [g for g in settings["hooks"]["PreToolUse"] if "protected" not in json.dumps(g)]
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    result = setup(repo)

    commands = json.dumps(json.loads(path.read_text(encoding="utf-8"))["hooks"])
    assert 'hook\\" protected' in commands
    assert "rules-check" not in commands
    assert "+1 hooks" in result.stdout  # the plan line agrees with the notes (review round 1)
    assert "the protected hook isn't in .claude/settings.json and is added" in result.stdout
    assert "the rules-check hook is switched off in .claude/kit.toml and is removed" in result.stdout
    again = setup(repo)  # settled: nothing to add or remove the second time
    assert "isn't in .claude/settings.json" not in again.stdout and "is removed" not in again.stdout
    # On again: the note mustn't blame the owner for a removal the kit made (review round 2).
    toml.write_text(toml.read_text(encoding="utf-8").replace("rules_check = false", ""), encoding="utf-8")
    back_on = setup(repo)
    # The owner asked for it back: no advice on keeping it out (review of PR 31).
    assert "the rules-check hook is on in .claude/kit.toml and is added to .claude/settings.json" in back_on.stdout
    assert "isn't in .claude/settings.json" not in back_on.stdout
    assert "missing" not in back_on.stdout


def _drop_hook(repo, name):
    path = repo / ".claude" / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8"))
    for event, groups in list(settings["hooks"].items()):
        settings["hooks"][event] = [g for g in groups if f'hook\\" {name}' not in json.dumps(g)]
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


@pytest.mark.slow
def test_a_deleted_switchable_hook_comes_back_with_the_way_to_keep_it_out(tmp_path):
    """Second review of PR 31: the advice itself had no test."""
    repo = new_repo(tmp_path)
    setup(repo)
    _drop_hook(repo, "lane-router")
    result = setup(repo)
    assert (
        "the lane-router hook isn't in .claude/settings.json and is added; "
        "to keep it out, set it false under [hooks] in .claude/kit.toml"
    ) in result.stdout


@pytest.mark.slow
def test_an_unrecorded_protected_hook_deleted_later_is_still_called_the_backstop(tmp_path):
    """Second review of PR 31: the owner's own copy of the protected hook is never recorded, so
    "not recorded" alone can't mean "switched back on"; protected has no switch."""
    repo = new_repo(tmp_path)
    command = 'sh "$CLAUDE_PROJECT_DIR/.claude/kit/hook" protected'
    own = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}]}}
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "settings.json").write_text(json.dumps(own, indent=2) + "\n", encoding="utf-8")
    setup(repo)
    _drop_hook(repo, "protected")
    result = setup(repo)
    assert "is on in .claude/kit.toml" not in result.stdout
    assert (
        "the protected hook isn't in .claude/settings.json and is added; it is the security backstop" in result.stdout
    )


@pytest.mark.slow
@pytest.mark.parametrize(
    "key, name, event",
    [("rules_check", "rules-check", "PostToolUse"), ("lane_router", "lane-router", "SessionStart")],
)
def test_a_switched_off_hook_the_owner_edited_is_kept_and_reported(tmp_path, key, name, event):
    repo = new_repo(tmp_path)
    setup(repo)
    path = repo / ".claude" / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8"))
    settings["hooks"][event][0]["hooks"][0]["timeout"] = 90
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    toml = repo / ".claude" / "kit.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + f"\n[hooks]\n{key} = false\n", encoding="utf-8")

    result = setup(repo)

    assert name in json.dumps(json.loads(path.read_text(encoding="utf-8"))["hooks"])
    assert f"the {name} hook is switched off" in result.stdout and "still runs your copy" in result.stdout


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
