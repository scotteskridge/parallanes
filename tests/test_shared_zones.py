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


def project(*lines):
    """RULES_TOML with extra [project] keys."""
    return RULES_TOML.replace('integration_branch = "main"', "\n".join(['integration_branch = "main"', *lines]))


ASK_ONLY = """
[[shared]]
paths = ["/.gitignore", "/package.json"]
mode = "ask"
"""


def test_shared_tables_add_to_the_defaults(tmp_path):
    # The trial's F8 fix is one repo-wide `ask` table: writing only that must keep every default
    # shared path, or each lane's wrap-up commit touching plans or fragments is refused.
    loaded = settings(tmp_path, LANES + ASK_ONLY)
    assert loaded.shared == (Zone(("/.gitignore", "/package.json"), "ask"), *shared_zones.DEFAULT_ZONES)
    assert loaded.shared_paths == ["/.gitignore", "/package.json", *shared_zones.paths_of(shared_zones.DEFAULT_ZONES)]
    matcher = shared_zones.Matcher(loaded.shared)
    assert matcher.find("docs/plans/a.md").mode == "open"
    assert matcher.find("docs/changelog.d/a.md").mode == "append"


def test_tables_come_first_so_errors_number_them_as_written(tmp_path):
    loaded = settings(tmp_path, LANES + ZONES)
    assert loaded.shared[:2] == (
        Zone(("docs/changelog.d/**",), "append"),
        Zone(("/.gitignore", "/package.json"), "ask", "platform"),
    )
    assert loaded.shared[2:] == shared_zones.DEFAULT_ZONES


def test_a_table_makes_a_default_stricter(tmp_path):
    loaded = settings(tmp_path, LANES + '[[shared]]\npaths = ["docs/plans/**"]\nmode = "ask"\n')
    assert shared_zones.Matcher(loaded.shared).find("docs/plans/a.md").mode == "ask"


def test_a_table_repeating_a_default_is_dropped(tmp_path):
    # The plan-13 template said to uncomment the default tables too: doing so still loads, unchanged.
    repeated = '[[shared]]\npaths = ["docs/changelog.d/**", "docs/health/**"]\nmode = "append"\n'
    assert settings(tmp_path, LANES + repeated).shared == shared_zones.DEFAULT_ZONES


def test_shared_defaults_false_drops_the_defaults(tmp_path):
    loaded = load(make_repo(tmp_path, config=project("shared_defaults = false") + LANES + ASK_ONLY)).lane_settings
    assert loaded.shared == (Zone(("/.gitignore", "/package.json"), "ask"),)
    assert loaded.shared_paths == ["/.gitignore", "/package.json"]


def test_shared_defaults_false_alone_shares_nothing(tmp_path):
    loaded = load(make_repo(tmp_path, config=project("shared_defaults = false") + LANES)).lane_settings
    assert (loaded.shared, loaded.shared_paths) == ((), [])


def test_shared_paths_and_tables_together_still_replace_the_defaults(tmp_path):
    loaded = load(make_repo(tmp_path, config=project('shared_paths = ["docs/**"]') + LANES + ZONES)).lane_settings
    assert loaded.shared[-1] == Zone(("docs/**",), "open")
    assert loaded.shared_paths == ["docs/changelog.d/**", "/.gitignore", "/package.json", "docs/**"]


def test_shared_defaults_true_keeps_them_beside_a_shared_paths_list(tmp_path):
    text = project('shared_paths = ["src/generated/**"]', "shared_defaults = true")
    loaded = load(make_repo(tmp_path, config=text + LANES)).lane_settings
    assert loaded.shared == (Zone(("src/generated/**",), "open"), *shared_zones.DEFAULT_ZONES)


def test_an_empty_shared_paths_list_still_shares_nothing(tmp_path):
    loaded = load(make_repo(tmp_path, config=project("shared_paths = []") + LANES)).lane_settings
    assert (loaded.shared, loaded.shared_paths) == ((), [])


def test_shared_defaults_must_be_a_boolean(tmp_path):
    with pytest.raises(ConfigError, match="shared_defaults"):
        load(make_repo(tmp_path, config=project('shared_defaults = "no"') + LANES))


def test_the_boundary_reads_shared_defaults_from_the_base_kit_toml_and_checks_its_type():
    # Review round 1 (both reviewers): lanes_only type-checked only LaneSettings fields, so
    # `shared_defaults = "false"` (a string, truthy) kept the defaults at the boundary unnoticed.
    assert lanes_only(project("shared_defaults = false") + LANES, "core").lane_settings.shared == ()
    for bad in ('"false"', "0"):
        with pytest.raises(ConfigError, match="shared_defaults"):
            lanes_only(project(f"shared_defaults = {bad}") + LANES, "core")


def test_steward_errors_number_tables_as_written_with_the_defaults_on(tmp_path):
    # Review round 1 (both reviewers): dropping a table that repeated an earlier table shifted the
    # numbers of every table after it.
    table = '[[shared]]\npaths = ["/a"]\nmode = "ask"\nsteward = "core"\n'
    bad = '[[shared]]\npaths = ["/x"]\nmode = "ask"\nsteward = "nope"\n'
    for name in ("one", "two"):
        (tmp_path / name).mkdir()
    assert "[[shared]] #2: steward 'nope'" in config_error(tmp_path / "one", LANES + table + bad)
    assert "[[shared]] #3: steward 'nope'" in config_error(tmp_path / "two", LANES + table + table + bad)


@pytest.mark.parametrize(
    "table",
    [
        '[[shared]]\npaths = ["docs/changelog.d/**", "docs/health/**"]\nmode = "append"\nsteward = "core"\n',
        '[[shared]]\npaths = ["docs/changelog.d/**"]\nmode = "ask"\nsteward = "core"\n',
        '[[shared]]\npaths = ["docs/changelog.d/**"]\nmode = "open"\n',
    ],
)
def test_a_table_cant_give_a_default_path_a_steward_or_loosen_it(tmp_path, table):
    # Review round 1 (general reviewer): the default zone still matched, so the steward was asked
    # anyway, the very config plan 13's template invited ("uncomment the defaults", add a steward).
    message = config_error(tmp_path, LANES + table)
    assert "[[shared]] #1" in message and "'docs/changelog.d/**'" in message
    assert "shared_defaults = false" in message
    # With the defaults off the same table is what the project gets.
    (tmp_path / "off").mkdir()
    loaded = load(make_repo(tmp_path / "off", config=project("shared_defaults = false") + LANES + table)).lane_settings
    assert len(loaded.shared) == 1


def test_a_written_table_repeating_a_default_path_loads_when_it_is_stricter(tmp_path):
    table = '[[shared]]\npaths = ["docs/changelog.d/**", "/x"]\nmode = "ask"\n'
    loaded = settings(tmp_path, LANES + table)
    assert shared_zones.Matcher(loaded.shared).find("docs/changelog.d/a.md").mode == "ask"


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
