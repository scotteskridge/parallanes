"""`[[shared]]` zones: open, append or ask, with an optional steward lane (decision 116)."""

import pytest

from helpers import RULES_TOML, make_repo
from kitlib import shared_zones
from kitlib.config import ConfigError, LaneSettings, lanes_only, load
from kitlib.shared_zones import Zone

LANES = """
[[lanes]]
name = "core"
owns = ["src/core/**"]

[[lanes]]
name = "platform"
owns = ["infra/**"]
"""

ZONES = """
[[shared]]
paths = ["docs/changelog.d/**"]
mode = "append"

[[shared]]
paths = ["/.gitignore", "/package.json"]
mode = "ask"
steward = "platform"
"""


def settings(tmp_path, text):
    return load(make_repo(tmp_path, config=RULES_TOML + text)).lane_settings


def config_error(tmp_path, text):
    # A bare top-level key must come before every table, or TOML reads it as the last table's.
    top, tables = (text, "") if text.startswith("shared =") else ("", text)
    with pytest.raises(ConfigError) as caught:
        load(make_repo(tmp_path, config=top + RULES_TOML + tables))
    message = str(caught.value)
    assert "kit.toml" in message
    return message


# ---- loading --------------------------------------------------------------------------------------


def test_defaults_give_fragments_and_reports_append_and_the_rest_open(tmp_path):
    loaded = settings(tmp_path, LANES)
    assert loaded.shared == shared_zones.DEFAULT_ZONES == LaneSettings().shared
    assert {zone.mode: set(zone.paths) for zone in loaded.shared} == {
        "append": {"docs/changelog.d/**", "docs/health/**"},
        "open": {"docs/backlog/**", "docs/plans/**", "docs/design/decisions-log.md"},
    }
    # Every default path is still shared with every lane, in the order v0.1 listed them.
    assert loaded.shared_paths == LaneSettings().shared_paths


def test_a_v01_shared_paths_list_stays_open_and_replaces_the_defaults(tmp_path):
    text = RULES_TOML.replace('integration_branch = "main"', 'integration_branch = "main"\nshared_paths = ["docs/**"]')
    loaded = load(make_repo(tmp_path, config=text + LANES)).lane_settings
    assert loaded.shared == (Zone(("docs/**",), "open"),)
    assert loaded.shared_paths == ["docs/**"]


def test_shared_tables_replace_the_defaults(tmp_path):
    loaded = settings(tmp_path, LANES + ZONES)
    assert loaded.shared == (
        Zone(("docs/changelog.d/**",), "append"),
        Zone(("/.gitignore", "/package.json"), "ask", "platform"),
    )
    assert loaded.shared_paths == ["docs/changelog.d/**", "/.gitignore", "/package.json"]


def test_shared_paths_and_tables_together(tmp_path):
    text = RULES_TOML.replace('integration_branch = "main"', 'integration_branch = "main"\nshared_paths = ["docs/**"]')
    loaded = load(make_repo(tmp_path, config=text + LANES + ZONES)).lane_settings
    assert loaded.shared[-1] == Zone(("docs/**",), "open")
    assert loaded.shared_paths == ["docs/changelog.d/**", "/.gitignore", "/package.json", "docs/**"]


def test_lane_settings_built_from_shared_paths_alone_are_open():
    assert LaneSettings(shared_paths=["a/**"]).shared == (Zone(("a/**",), "open"),)
    assert LaneSettings(shared_paths=[]).shared == ()


@pytest.mark.parametrize(
    "text, expected",
    [
        ('[[shared]]\nmode = "open"\n', "missing required key 'paths'"),
        ('[[shared]]\npaths = []\nmode = "open"\n', "'paths' must list at least one glob"),
        ('[[shared]]\npaths = ["a[]"]\nmode = "open"\n', "'paths'"),
        ('[[shared]]\npaths = [1]\nmode = "open"\n', "'paths'"),
        ('[[shared]]\npaths = ["a/**"]\n', "missing required key 'mode'"),
        ('[[shared]]\npaths = ["a/**"]\nmode = "escalate"\n', "'open', 'append', 'ask'"),
        (
            '[[shared]]\npaths = ["a/**"]\nmode = "ask"\nsteward = "nobody"\n',
            "[[shared]] #1: steward 'nobody' is not a lane",
        ),
        ('[[shared]]\npaths = ["a/**"]\nmode = "ask"\nsteward = 3\n', "'steward'"),
        ('[[shared]]\npaths = ["a/**"]\nmode = "open"\nsteward = "core"\n', "open"),
        ('[[shared]]\npaths = ["a/**"]\nmode = "ask"\nowner = "core"\n', "'owner'"),
        ("shared = 3\n", "[[shared]]"),
        ('shared = ["a/**"]\n', "[[shared]] #1"),
    ],
)
def test_shared_errors_name_the_key(tmp_path, text, expected):
    message = config_error(tmp_path, text if text.startswith("shared =") else LANES + "\n" + text)
    assert expected in message, message


def test_a_steward_is_checked_against_the_lanes_of_an_older_kit_toml_too():
    text = RULES_TOML + LANES + ZONES
    assert lanes_only(text, "core").lane_settings.shared[1].steward == "platform"
    with pytest.raises(ConfigError, match="'platform' is not a lane"):
        lanes_only(text.replace('name = "platform"', 'name = "infra"'), "core")


# ---- matching -------------------------------------------------------------------------------------


def test_the_stricter_zone_wins_whatever_the_order():
    zones = (Zone(("docs/**",), "open"), Zone(("docs/changelog.d/**",), "append"), Zone(("docs/**/*.md",), "ask"))
    for ordered in (zones, zones[::-1]):
        matcher = shared_zones.Matcher(ordered)
        assert matcher.find("docs/changelog.d/a.md") == shared_zones.Match("ask", None, "docs/**/*.md")
        assert matcher.find("docs/changelog.d/a.txt") == shared_zones.Match("append", None, "docs/changelog.d/**")
        assert matcher.find("docs/x.txt") == shared_zones.Match("open", None, "docs/**")
        assert matcher.find("src/a.py") is None


def test_a_steward_skips_only_its_own_zones():
    # Review round 1 (both reviewers): a stricter zone's steward used to loosen a broader zone with
    # none, so lane platform rewrote an existing .gitignore that `/.git*` (append) would have asked about.
    ask = Zone(("/.gitignore",), "ask", "platform")
    broader = shared_zones.Matcher((ask, Zone(("/.git*",), "append")))
    assert broader.find(".gitignore", "platform") == shared_zones.Match("append", None, "/.git*")
    assert broader.find(".gitignore", "core") == shared_zones.Match("ask", "platform", "/.gitignore")
    assert shared_zones.Matcher((ask,)).find(".gitignore", "platform") is None  # nothing else applies
    other = shared_zones.Matcher((ask, Zone(("/.git*",), "ask", "core")))
    assert other.find(".gitignore", "platform") == shared_zones.Match("ask", "core", "/.git*")
    assert other.find(".gitignore", "api").steward is None  # two stewards: the message names neither
    assert shared_zones.Matcher((ask, Zone(("/.git*",), "open"))).find(".gitignore", "platform").mode == "open"
