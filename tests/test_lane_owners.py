"""Who owns a file two lanes claim (decision 97): the most specific pattern wins; order never matters.

The rule is lanekeeper's (docs/survey-lanekeeper.md); these run in-process on path lists (fast set).
"""

import os
from types import SimpleNamespace

import pytest

from kitlib import lane_owners
from kitlib.config import Lane, LaneSettings

APP = Lane(name="app", owns=["src/**"], scope="", resources={})
CORE = Lane(name="core", owns=["src/core/**", "tests/core/**"], scope="", resources={})
DOCS = Lane(name="docs", owns=["*.md"], scope="", resources={})


def config(*lanes, shared=()):
    return SimpleNamespace(lanes=list(lanes), lane_settings=LaneSettings(shared_paths=list(shared)))


@pytest.mark.parametrize(
    "pattern, score",
    [
        ("**", (0, 2)),
        ("src/**", (1, 6)),
        ("src/", (1, 6)),  # a trailing / means everything inside: the same as src/**
        ("/src/**", (1, 6)),
        ("src/core/**", (2, 11)),
        ("src/*.py", (1, 8)),
        ("src/a[bc]/x.py", (2, 14)),  # a [class] is a wildcard, so its segment doesn't count
        ("Makefile", (1, 8)),
        ("*.md", (0, 4)),
    ],
)
def test_specificity_counts_wildcard_free_segments_then_length(pattern, score):
    assert lane_owners.specificity(pattern) == score


@pytest.mark.parametrize("lanes", [(APP, CORE), (CORE, APP)])
def test_the_more_specific_pattern_wins_whatever_the_order(lanes):
    claim = lane_owners.claim(config(*lanes), "src/core/a.py")
    assert claim.owner == "core" and claim.pattern == "src/core/**"
    assert claim.losers == (("app", "src/**"),)
    assert lane_owners.claim(config(*lanes), "src/ui/b.py").owner == "app"


def test_a_lane_is_judged_by_its_best_matching_pattern():
    wide = Lane(name="wide", owns=["**", "src/core/deep/**"], scope="", resources={})
    assert lane_owners.claim(config(wide, CORE), "src/core/deep/x.py").owner == "wide"
    assert lane_owners.claim(config(wide, CORE), "src/core/x.py").owner == "core"


def test_longer_pattern_breaks_an_equal_segment_count():
    # Both have one wildcard-free segment; `src/*.py` is longer than `src/**`.
    py = Lane(name="py", owns=["src/*.py"], scope="", resources={})
    assert lane_owners.claim(config(APP, py), "src/a.py").owner == "py"


def test_different_patterns_can_still_tie_on_a_real_file():
    a = Lane(name="a", owns=["src/*.py"], scope="", resources={})
    b = Lane(name="b", owns=["src/a.p*"], scope="", resources={})
    claim = lane_owners.claim(config(a, b), "src/a.py")
    assert claim.owner is None and claim.tied == (("a", "src/*.py"), ("b", "src/a.p*"))
    assert lane_owners.claim(config(a, b), "src/b.py").owner == "a"


def test_no_lane_and_one_lane():
    assert lane_owners.claim(config(APP, CORE), "README.md") == lane_owners.Claim(None, None, (), ())
    claim = lane_owners.claim(config(APP, CORE), "tests/core/t.py")
    assert (claim.owner, claim.losers, claim.tied) == ("core", (), ())


def test_why_not_is_none_for_owned_and_shared_files():
    cfg = config(APP, CORE, shared=["src/core/shared/**"])
    assert lane_owners.why_not(cfg, CORE, "src/core/a.py") is None
    assert lane_owners.why_not(cfg, APP, "src/core/shared/x.py") is None  # shared paths come first


def test_why_not_names_the_owner_and_why_it_wins():
    reason = lane_owners.why_not(config(APP, CORE), APP, "src/core/a.py")
    assert reason == "owned by lane 'core' (src/core/** is more specific than src/**)"
    assert lane_owners.why_not(config(APP, CORE), CORE, "src/ui/b.py") == "owned by lane 'app'"
    assert lane_owners.why_not(config(APP, CORE), CORE, "README.md") == "no lane owns it"


def test_why_not_refuses_a_tie_for_every_lane_in_it():
    a = Lane(name="a", owns=["src/*.py"], scope="", resources={})
    b = Lane(name="b", owns=["src/a.p*"], scope="", resources={})
    for lane in (a, b):
        reason = lane_owners.why_not(config(a, b), lane, "src/a.py")
        assert "lanes 'a' and 'b' claim it equally" in reason and "more specific" in reason


@pytest.mark.skipif(os.name != "nt", reason="the Windows file system ignores case, so ownership does too")
def test_case_is_ignored_on_windows():
    assert lane_owners.claim(config(APP, CORE), "SRC/Core/A.py").owner == "core"


# ---- the same pattern in two lanes: an error when kit.toml loads ------------------------------------


@pytest.mark.parametrize("other", ["src/**", "src/", "/src/**"])
def test_the_same_pattern_in_two_lanes_is_found(other):
    twin = Lane(name="twin", owns=["lib/**", other], scope="", resources={})
    assert lane_owners.same_pattern(config(APP, twin).lanes) == ("app", "twin", "src/**", other)


def test_one_lane_repeating_its_own_pattern_is_not_a_tie():
    twice = Lane(name="twice", owns=["src/**", "src/"], scope="", resources={})
    assert lane_owners.same_pattern([twice, CORE]) is None


@pytest.mark.skipif(os.name != "nt", reason="the Windows file system ignores case, so ownership does too")
def test_the_same_pattern_ignores_case_on_windows():
    twin = Lane(name="twin", owns=["SRC/**"], scope="", resources={})
    assert lane_owners.same_pattern([APP, twin]) is not None


# ---- the overlap report for `lanes create` and `lanes status` ---------------------------------------


def test_overlaps_group_files_by_who_wins():
    files = ["src/core/a.py", "src/core/b.py", "src/ui/c.py", "README.md", "tests/core/t.py"]
    notes, problems = lane_owners.overlaps(config(APP, CORE), files)
    assert notes == ["src/core/** (core) wins over src/** (app): 2 files, e.g. src/core/a.py"]
    assert problems == []


def test_overlaps_skip_shared_files_and_say_one_file():
    files = ["src/core/a.py", "src/core/shared/x.py"]
    notes, _ = lane_owners.overlaps(config(APP, CORE, shared=["src/core/shared/**"]), files)
    assert notes == ["src/core/** (core) wins over src/** (app): 1 file, e.g. src/core/a.py"]


def test_overlaps_report_ties_as_problems():
    a = Lane(name="a", owns=["src/*.py"], scope="", resources={})
    b = Lane(name="b", owns=["src/a.p*"], scope="", resources={})
    notes, problems = lane_owners.overlaps(config(a, b), ["src/a.py", "src/b.py"])
    assert notes == []
    assert problems == [
        "src/*.py (a) and src/a.p* (b) claim 1 file equally, e.g. src/a.py: no lane owns it until one "
        "pattern in .claude/kit.toml is more specific"
    ]


def test_no_overlaps_for_separate_lanes():
    assert lane_owners.overlaps(config(CORE, DOCS), ["src/core/a.py", "README.md"]) == ([], [])
