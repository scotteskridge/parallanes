"""`[[lanes]]` and the lane keys of `[project]` are validated strictly (decision 42)."""

import pytest

from helpers import RULES_TOML, make_repo
from kitlib.config import ConfigError, load

LANES_TOML = (
    RULES_TOML.replace(
        'integration_branch = "main"',
        'integration_branch = "main"\nmerge_mode = "local"\nworktree_root = "../{project}-lanes"\n'
        'ownership = "off"\nshared_paths = ["docs/plans/**"]',
    )
    + """
[[lanes]]
name = "core"
scope = "Domain logic"
owns = ["src/core/**", "tests/core/**"]
resources = { dev_port = 8001, editor = "a", headless = true }

[[lanes]]
name = "api-2"
owns = ["src/api/**"]
"""
)


def test_lanes_load(tmp_path):
    config = load(make_repo(tmp_path, config=LANES_TOML))
    core, api = config.lanes
    assert (core.name, core.scope, core.owns) == ("core", "Domain logic", ["src/core/**", "tests/core/**"])
    assert core.resources == {"dev_port": 8001, "editor": "a", "headless": True}
    assert (api.name, api.scope, api.owns, api.resources) == ("api-2", "", ["src/api/**"], {})
    settings = config.lane_settings
    assert settings.integration_branch == "main"
    assert settings.merge_mode == "local"
    assert settings.worktree_root == "../{project}-lanes"
    assert settings.ownership == "off"
    assert settings.shared_paths == ["docs/plans/**"]


def test_lane_defaults(tmp_path):
    config = load(make_repo(tmp_path, config="[project]\nname = 'demo'\n"))
    assert config.lanes == []
    settings = config.lane_settings
    assert (settings.integration_branch, settings.merge_mode, settings.worktree_root, settings.ownership) == (
        "main",
        "pr",
        ".claude/worktrees",
        "ask",
    )
    assert settings.shared_paths == [
        "docs/changelog.d/**",
        "docs/backlog/**",
        "docs/plans/**",
        "docs/design/decisions-log.md",
        "docs/health/**",
    ]


def config_error(tmp_path, text):
    with pytest.raises(ConfigError) as caught:
        load(make_repo(tmp_path, config=text))
    return str(caught.value)


@pytest.mark.parametrize(
    "lanes, expected",
    [
        ('[[lanes]]\nowns = ["a/**"]\n', "missing required key 'name'"),
        ('[[lanes]]\nname = "core"\n', "'owns'"),
        ('[[lanes]]\nname = "core"\nowns = []\n', "'owns'"),
        ('[[lanes]]\nname = "Core"\nowns = ["a/**"]\n', "'Core'"),
        ('[[lanes]]\nname = "ui/x"\nowns = ["a/**"]\n', "'ui/x'"),
        ('[[lanes]]\nname = "-ui"\nowns = ["a/**"]\n', "'-ui'"),
        ('[[lanes]]\nname = "main"\nowns = ["a/**"]\n', "integration branch"),
        ('[[lanes]]\nname = "a"\nowns = ["a/**"]\n[[lanes]]\nname = "a"\nowns = ["b/**"]\n', "duplicate lane"),
        ('[[lanes]]\nname = "a"\nowns = ["a/**"]\n[[lanes]]\nname = "b"\nowns = ["/a/"]\n', "'a' and 'b' both own"),
        ('[[lanes]]\nname = "a"\nowns = ["x[]"]\n', "'owns'"),
        ('[[lanes]]\nname = "a"\nowns = ["a/**"]\nowner = "me"\n', "'owner'"),
        ('[[lanes]]\nname = "a"\nowns = "a/**"\n', "'owns'"),
        ('[[lanes]]\nname = "a"\nowns = ["a/**"]\nscope = 3\n', "'scope'"),
        ('[[lanes]]\nname = "a"\nowns = ["a/**"]\nresources = { x = [1] }\n', "'resources'"),
        ('[[lanes]]\nname = "a"\nowns = ["a/**"]\nresources = 5\n', "'resources'"),
        ("lanes = 3\n", "lanes"),
    ],
)
def test_lane_errors_name_the_key(tmp_path, lanes, expected):
    message = config_error(tmp_path, RULES_TOML + "\n" + lanes)
    assert expected in message, message
    assert "kit.toml" in message


@pytest.mark.parametrize(
    "old, new, expected",
    [
        ('integration_branch = "main"', 'integration_branch = "main"\nmerge_mode = "squash"', "merge_mode"),
        ('integration_branch = "main"', 'integration_branch = "main"\nownership = "deny"', "ownership"),
        ('integration_branch = "main"', 'integration_branch = "main"\nshared_paths = ["a[]"]', "shared_paths"),
        ('integration_branch = "main"', 'integration_branch = "main"\nshared_paths = [1]', "shared_paths"),
        ('integration_branch = "main"', 'integration_branch = "main"\nworktree_root = ""', "worktree_root"),
        ('integration_branch = "main"', 'integration_branch = ""', "integration_branch"),
    ],
)
def test_project_lane_keys_are_validated(tmp_path, old, new, expected):
    message = config_error(tmp_path, RULES_TOML.replace(old, new))
    assert expected in message, message


@pytest.mark.parametrize("name", ["con", "aux", "nul", "prn", "com1", "lpt9"])
def test_windows_device_names_are_rejected(tmp_path, name):
    message = config_error(tmp_path, RULES_TOML + f'\n[[lanes]]\nname = "{name}"\nowns = ["a/**"]\n')
    assert repr(name) in message and "Windows" in message


def test_unknown_worktree_root_placeholder_is_rejected(tmp_path):
    text = RULES_TOML.replace(
        'integration_branch = "main"', 'integration_branch = "main"\nworktree_root = "../{name}-lanes"'
    )
    assert "{name}" in config_error(tmp_path, text)
