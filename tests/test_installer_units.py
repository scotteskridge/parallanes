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
