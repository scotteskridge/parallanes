"""Deny and ask rules generated from [protected] into .claude/settings.json (decisions 29-31)."""
import json

import pytest

from helpers import RULES_TOML, make_repo, run_cli, write
from kitlib.config import Protected
from kitlib.settings import RECORD_REL, expected_rules

PROTECTED_TOML = RULES_TOML + """
[protected]
paths = ["vendor/**", "docs/originals/", "*.lock", "build/"]
commands = ["git push --force"]
secrets = [".env", "config/keys/*"]
"""


def test_paths_are_root_anchored_and_keep_their_meaning():
    rules = expected_rules(Protected(paths=["vendor/**", "docs/originals/", "*.lock", "build/", "/top.txt"]))
    assert rules["deny"][:5] == [
        "Edit(/vendor/**)",  # anchored: a bare vendor/** deny would match vendor/ at any depth
        "Edit(/docs/originals/**)",
        "Edit(/**/*.lock)",  # no slash: any depth, as in kit.toml
        "Edit(/**/build/**)",  # a lone trailing slash matches at any depth, as in gitignore
        "Edit(/top.txt)",
    ]


def test_secrets_deny_read_and_edit():
    rules = expected_rules(Protected(secrets=[".env", "config/keys/*"], commands=[]))
    assert rules["deny"] == ["Read(.env)", "Edit(.env)", "Read(/config/keys/*)", "Edit(/config/keys/*)"]


def test_commands_cover_bash_and_powershell():
    rules = expected_rules(Protected(commands=["git push --force"], secrets=[]))
    assert rules["deny"] == ["Bash(git push --force *)", "PowerShell(git push --force *)"]


def test_kit_config_gets_ask_rules_unless_switched_off():
    asks = expected_rules(Protected())["ask"]
    assert asks == ["Edit(/.claude/settings.json)", "Edit(/.claude/kit.toml)", "Edit(/.claude/kit/**)", "Edit(/.githooks/**)"]
    assert expected_rules(Protected(guard_kit=False))["ask"] == []


def read_settings(repo):
    return json.loads((repo / ".claude" / "settings.json").read_text(encoding="utf-8"))


def sync(repo, *extra):
    return run_cli(repo, "settings", "sync", *extra)


def test_sync_creates_settings_and_the_record(tmp_path):
    repo = make_repo(tmp_path, config=PROTECTED_TOML, settings=False)
    result = sync(repo)
    assert result.returncode == 0, result.stderr
    settings = read_settings(repo)
    assert "Edit(/vendor/**)" in settings["permissions"]["deny"]
    assert "Edit(/.claude/kit.toml)" in settings["permissions"]["ask"]
    record = json.loads((repo / RECORD_REL).read_text(encoding="utf-8"))
    assert record["deny"] == settings["permissions"]["deny"]
    assert b"\r\n" not in (repo / ".claude" / "settings.json").read_bytes()
    assert "added" in result.stdout


def test_sync_keeps_owner_rules_and_other_keys(tmp_path):
    repo = make_repo(tmp_path, config=PROTECTED_TOML, settings=False)
    owner = {
        "model": "opus",
        "permissions": {"allow": ["Bash(npm test)"], "deny": ["Read(/secrets/**)"], "defaultMode": "default"},
        "hooks": {"PreToolUse": []},
    }
    write(repo, ".claude/settings.json", json.dumps(owner, indent=4))
    assert sync(repo).returncode == 0
    settings = read_settings(repo)
    assert list(settings) == ["model", "permissions", "hooks"]  # key order kept
    assert settings["permissions"]["allow"] == ["Bash(npm test)"]
    assert settings["permissions"]["deny"][0] == "Read(/secrets/**)"
    assert settings["permissions"]["defaultMode"] == "default"


def test_sync_is_idempotent(tmp_path):
    repo = make_repo(tmp_path, config=PROTECTED_TOML, settings=False)
    sync(repo)
    before = (repo / ".claude" / "settings.json").read_bytes()
    result = sync(repo)
    assert (repo / ".claude" / "settings.json").read_bytes() == before
    assert "up to date" in result.stdout


def test_sync_removes_only_rules_it_wrote(tmp_path):
    repo = make_repo(tmp_path, config=PROTECTED_TOML, settings=False)
    sync(repo)
    settings = read_settings(repo)
    settings["permissions"]["deny"].append("Edit(/owner/**)")
    write(repo, ".claude/settings.json", json.dumps(settings))
    write(repo, ".claude/kit.toml", PROTECTED_TOML.replace('"vendor/**", ', ""))
    result = sync(repo)
    deny = read_settings(repo)["permissions"]["deny"]
    assert "Edit(/vendor/**)" not in deny
    assert "Edit(/owner/**)" in deny
    assert "removed" in result.stdout


def test_dry_run_writes_nothing(tmp_path):
    repo = make_repo(tmp_path, config=PROTECTED_TOML, settings=False)
    result = sync(repo, "--dry-run")
    assert result.returncode == 0
    assert "Edit(/vendor/**)" in result.stdout
    assert not (repo / ".claude" / "settings.json").exists()
    assert not (repo / RECORD_REL).exists()


@pytest.mark.parametrize(
    "text",
    ["{not json", "[]", '{"permissions": []}', '{"permissions": {"deny": "Edit(x)"}}', '{"permissions": {"ask": [1]}}'],
)
def test_unusable_settings_are_never_overwritten(tmp_path, text):
    repo = make_repo(tmp_path, config=PROTECTED_TOML, settings=False)
    write(repo, ".claude/settings.json", text)
    result = sync(repo)
    assert result.returncode == 2
    assert "settings.json" in result.stderr
    assert (repo / ".claude" / "settings.json").read_text(encoding="utf-8") == text


def test_settings_with_a_byte_order_mark_are_read(tmp_path):
    repo = make_repo(tmp_path, config=PROTECTED_TOML, settings=False)
    (repo / ".claude" / "settings.json").write_bytes(b"\xef\xbb\xbf{}")
    assert sync(repo).returncode == 0


def test_check_settings_flags_missing_and_stale_rules(tmp_path):
    repo = make_repo(tmp_path, config=PROTECTED_TOML, settings=False)
    missing = run_cli(repo, "check", "settings")
    assert missing.returncode == 1
    assert "Edit(/vendor/**)" in missing.stdout and "settings sync" in missing.stdout

    sync(repo)
    assert run_cli(repo, "check", "settings").returncode == 0

    write(repo, ".claude/kit.toml", PROTECTED_TOML.replace('"vendor/**", ', ""))
    stale = run_cli(repo, "check", "settings")
    assert stale.returncode == 1
    assert "Edit(/vendor/**)" in stale.stdout and "no longer" in stale.stdout


def test_check_settings_counts_an_owner_rule_that_covers_it(tmp_path):
    # The owner wrote the same rule by hand before the kit was installed: that's not drift.
    repo = make_repo(tmp_path, config=PROTECTED_TOML, settings=False)
    sync(repo)
    record = repo / RECORD_REL
    record.write_text('{"deny": [], "ask": []}', encoding="utf-8")
    assert run_cli(repo, "check", "settings").returncode == 0


def test_check_all_includes_settings(tmp_path):
    repo = make_repo(tmp_path, config=PROTECTED_TOML, settings=False)
    result = run_cli(repo, "check", "all")
    assert result.returncode == 1
    assert "settings sync" in result.stdout
