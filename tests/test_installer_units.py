"""The installer's pieces (plan 08, decisions 99-101): managed blocks, values, hook wiring.

Whole installs, run as a process, are in test_installer.py.
"""

import json
import tomllib

import pytest

from installer import blocks, settings_hooks, values

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


# ---- review round 1 ---------------------------------------------------------------------------


def test_block_leaves_the_owners_line_endings_alone():
    """Mixed endings stay as they were; only the block's own lines use the file's first ending."""
    owner = "a\r\nb\nc\r\n"
    merged = blocks.merge(owner, "x\n")
    assert merged.startswith(owner)


def test_block_keeps_a_utf8_bom():
    merged = blocks.merge("﻿a\n", "x\n")
    assert merged.startswith("﻿a\n")


def test_owner_lines_outside_the_block_are_found():
    assert blocks.outside(blocks.merge("", "x\n")) == []
    assert blocks.outside(blocks.merge("*.sln eol=crlf\n", "x\n")) == ["*.sln eol=crlf"]


def test_an_owner_edited_kit_hook_is_not_added_again():
    """Raising a kit hook's timeout must not make the next run append a second copy."""
    settings = {}
    record = json.loads(json.dumps(settings_hooks.merge(settings, [])))  # as read back from the manifest
    settings["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] = 90
    settings_hooks.merge(settings, record)
    commands = [group["hooks"][0]["command"] for group in settings["hooks"]["PreToolUse"]]
    assert len(commands) == len(set(commands)) == 2


@pytest.mark.parametrize(
    "recorded",
    [[{"event": "PreToolUse"}], [{"group": {}}], ["x"], [{"event": 1, "group": {}}]],
)
def test_a_malformed_hook_record_is_an_error(recorded):
    with pytest.raises(settings_hooks.HooksError):
        settings_hooks.merge({}, recorded)


# ---- switching hooks off ([hooks] in kit.toml) --------------------------------------------------


def _names(settings):
    return sorted(
        group["hooks"][0]["command"].rsplit(" ", 1)[-1] for groups in settings["hooks"].values() for group in groups
    )


def test_a_switched_off_hook_is_not_added():
    settings = {}
    record = settings_hooks.merge(settings, [], off={"rules-check", "lane-router"})
    assert _names(settings) == ["ownership", "protected"]
    assert "PostToolUse" not in settings["hooks"] and "SessionStart" not in settings["hooks"]
    assert len(record) == 2


def test_switching_a_hook_off_removes_the_kits_copy_and_on_again_restores_it():
    settings = {}
    record = settings_hooks.merge(settings, [])
    record = settings_hooks.merge(settings, record, off={"rules-check"})
    assert _names(settings) == ["lane-router", "ownership", "protected"]
    assert not any("rules-check" in json.dumps(entry) for entry in record)
    settings_hooks.merge(settings, record)
    assert _names(settings) == ["lane-router", "ownership", "protected", "rules-check"]


def test_a_switched_off_hook_the_owner_edited_is_kept_and_reported():
    """An edited copy is the owner's now: leave it, but say it still runs."""
    settings = {}
    record = json.loads(json.dumps(settings_hooks.merge(settings, [])))
    settings["hooks"]["PostToolUse"][0]["hooks"][0]["timeout"] = 90
    settings_hooks.merge(settings, record, off={"rules-check"})
    assert "rules-check" in _names(settings)
    assert settings_hooks.still_running(settings, {"rules-check"}) == ["rules-check"]
    assert settings_hooks.still_running(settings, set()) == []


def test_the_protected_hook_cant_be_switched_off():
    with pytest.raises(ValueError):
        settings_hooks.merge({}, [], off={"protected"})


def test_a_deleted_kit_hook_is_reported_when_it_comes_back():
    settings = {}
    settings_hooks.merge(settings, [])
    del settings["hooks"]["PreToolUse"][0]  # the protected hook
    assert settings_hooks.missing(settings) == ["protected"]
    # A deleted hook that is switched off doesn't come back, so it isn't reported.
    settings = {}
    settings_hooks.merge(settings, [])
    del settings["hooks"]["PostToolUse"]
    assert settings_hooks.missing(settings, off={"rules-check"}) == []
    assert settings_hooks.missing(settings) == ["rules-check"]


def test_a_hook_comes_back_said_aloud_even_when_it_was_never_recorded():
    """Review round 1: an owner-edited copy left unrecorded (off, then on), then deleted, still counts."""
    settings = {}
    record = json.loads(json.dumps(settings_hooks.merge(settings, [])))
    settings["hooks"]["PostToolUse"][0]["hooks"][0]["timeout"] = 90
    record = settings_hooks.merge(settings, record, off={"rules-check"})
    record = settings_hooks.merge(settings, record)  # on again: the edited copy stays the owner's
    del settings["hooks"]["PostToolUse"]
    assert settings_hooks.missing(settings) == ["rules-check"]


def test_a_kit_command_under_another_event_doesnt_count_as_present():
    """merge looks per event, so the report must too, or a second copy is added unannounced."""
    settings = {}
    settings_hooks.merge(settings, [])
    group = settings["hooks"]["PreToolUse"].pop(0)
    settings["hooks"]["PostToolUse"].append(group)
    assert settings_hooks.missing(settings) == ["protected"]


def test_recorded_names_tell_a_deleted_hook_from_one_switched_back_on():
    """Switching off drops a hook from the record; deleting it by hand doesn't (review of PR 31)."""
    settings = {}
    record = settings_hooks.merge(settings, [])
    assert settings_hooks.recorded_names(record) == {"protected", "ownership", "rules-check", "lane-router"}
    record = settings_hooks.merge(settings, record, off={"rules-check"})
    assert "rules-check" not in settings_hooks.recorded_names(record)
    del settings["hooks"]["SessionStart"]  # deleted by hand: still recorded
    assert "lane-router" in settings_hooks.recorded_names(record)


def test_every_switch_in_kit_toml_names_a_hook_the_kit_wires():
    """A typo in either list would make a switch silently do nothing."""
    from kitlib import config

    wired = {name for _, _, name in settings_hooks.WIRING}
    assert set(config._HOOK_SWITCHES.values()) <= wired - {settings_hooks.ALWAYS_ON}
    assert set(config._HOOK_REDIRECTS) | set(config._HOOK_SWITCHES.values()) == wired  # each one has a key or a pointer


# ---- review round 3 ---------------------------------------------------------------------------


@pytest.mark.parametrize("answers", [[(128, "")], [(1, ""), (128, "")], [(1, ""), (0, "")]])
def test_precommit_is_left_alone_when_git_cant_answer(tmp_path, monkeypatch, answers):
    """core.hooksPath switches off .git/hooks: if git can't say where the hooks are, don't set it."""
    from installer import main

    replies = iter(answers)
    monkeypatch.setattr(main, "_git", lambda target, *args: next(replies))
    assert main._plan_precommit(tmp_path, tmp_path, True) == "unknown"
