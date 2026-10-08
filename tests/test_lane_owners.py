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
    "pattern, canonical",
    [
        ("src/**", "src/**"),
        ("/src/**", "src/**"),
        ("/src/", "src/**"),  # a trailing / means everything inside
        ("src/**/*", "src/**"),
        ("src/", "**/src/**"),  # no other slash: a src folder at any depth (globs)
        ("*.py", "**/*.py"),  # a bare name matches at any depth
        ("**/*.py", "**/*.py"),
        ("main.py", "**/main.py"),
        ("/main.py", "main.py"),  # the leading / anchors it at the root
        ("*", "**"),
        ("**/**/x/**", "**/x/**"),
    ],
)
def test_patterns_that_match_the_same_files_have_one_canonical_form(pattern, canonical):
    assert lane_owners.canonical(pattern) == canonical


@pytest.mark.parametrize(
    "narrow, wide",
    [
        ("src/core/**", "src/**"),  # more wildcard-free segments
        ("src/*", "src/**"),  # review round 1: length gave these to the wider `**`
        ("src/*.py", "src/**/*.py"),
        ("src/**", "**/src/**"),
        ("/main.py", "main.py"),  # the root file only, against main.py at any depth
        ("src/*.py", "src/**"),
        ("src/a.py", "src/a.p?"),
        ("src/[a]pp/x", "src/*/x"),  # one wildcard each; the class leaves more literal characters
        ("Makefile", "*"),
        # Review round 2: a filter after `**` narrows it, so literal characters come before wildcards.
        ("*.md", "**"),
        ("src/**/*_test.py", "src/**"),
        ("tests/**/*.py", "tests/**"),
        ("src/a*", "src/a**"),  # `**` inside a segment still crosses folders
    ],
)
def test_the_narrower_pattern_is_more_specific(narrow, wide):
    assert lane_owners.specificity(narrow) > lane_owners.specificity(wide)


@pytest.mark.parametrize("a, b", [("src/*.py", "src/?.py"), ("src/*.py", "src/a.p*"), ("src/", "**/src/**")])
def test_equally_specific_patterns(a, b):
    assert lane_owners.specificity(a) == lane_owners.specificity(b)


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


def test_fewer_wildcards_break_an_equal_segment_count():
    # Both have one wildcard-free segment; `src/*.py` has no `**`.
    py = Lane(name="py", owns=["src/*.py"], scope="", resources={})
    assert lane_owners.claim(config(APP, py), "src/a.py").owner == "py"


def test_a_name_at_any_depth_doesnt_take_a_folder_lanes_files():
    # Review round 1: `conftest.py` and `build/` match at any depth, so they rank below `web/**`.
    web = Lane(name="web", owns=["web/**"], scope="", resources={})
    tools = Lane(name="tools", owns=["conftest.py", "build/"], scope="", resources={})
    assert lane_owners.claim(config(web, tools), "web/conftest.py").owner == "web"
    assert lane_owners.claim(config(web, tools), "web/build/out.js").owner == "web"
    assert lane_owners.claim(config(web, tools), "lib/conftest.py").owner == "tools"


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
    assert reason == "src/** matches it, but lane 'core' owns it: src/core/** is more specific"
    assert lane_owners.why_not(config(APP, CORE), CORE, "src/ui/b.py") == "owned by lane 'app'"
    assert lane_owners.why_not(config(APP, CORE), CORE, "README.md") == "no lane owns it"


def test_why_not_refuses_a_tie_for_every_lane_in_it():
    a = Lane(name="a", owns=["src/*.py"], scope="", resources={})
    b = Lane(name="b", owns=["src/a.p*"], scope="", resources={})
    for lane in (a, b):
        reason = lane_owners.why_not(config(a, b), lane, "src/a.py")
        assert "lanes 'a' and 'b' claim it equally" in reason and "more specific" in reason


# ---- the fix a lane stop offers (backlog ownership-fix-hint) -----------------------------------------


def widened(lane, line):
    """The lane with the `owns = [...]` line a fix offers, read the way kit.toml would read it."""
    import tomllib

    return Lane(name=lane.name, owns=tomllib.loads(line)["owns"], scope="", resources={})


def test_no_fix_when_the_lane_may_change_the_file_or_two_lanes_tie():
    cfg = config(APP, CORE, shared=["docs/**"])
    assert lane_owners.fix_for(cfg, CORE, "src/core/a.py") is None
    assert lane_owners.fix_for(cfg, CORE, "docs/x.md") is None
    a = Lane(name="a", owns=["src/*.py"], scope="", resources={})
    b = Lane(name="b", owns=["src/a.p*"], scope="", resources={})
    assert lane_owners.fix_for(config(a, b), a, "src/a.py") is None  # why_not already says how to settle it


def test_a_file_another_lane_owns_points_at_that_lane_and_never_widens():
    for fix in (
        lane_owners.fix_for(config(APP, CORE), CORE, "src/ui/b.py"),
        lane_owners.fix_for(config(APP, CORE), APP, "src/core/a.py"),  # lost on specificity: still core's
    ):
        assert "lane 'core'" in fix or "lane 'app'" in fix
        assert "owns =" not in fix and "change belongs in" in fix


def test_a_file_no_lane_owns_gets_the_exact_kit_toml_line():
    fix = lane_owners.fix_for(config(APP, CORE), CORE, ".gitignore")
    line = 'owns = ["src/core/**", "tests/core/**", "/.gitignore"]'
    assert fix == f"to let lane 'core' change it, its line in .claude/kit.toml becomes: {line}"
    # The trial's wall (F8, F11): the lane's own branch can't carry it; the stops say how it lands.
    assert "branch that isn't a lane's" in lane_owners.HOW_POLICY_LANDS
    assert "lanes sync" in lane_owners.HOW_POLICY_LANDS


@pytest.mark.filterwarnings("error")  # `[[]` once compiled to a regex Python warns will change meaning
@pytest.mark.parametrize(
    "path",
    [
        ".gitignore",  # bare: anchored, so a nested .gitignore stays out
        "data dir/notes v2.txt",  # spaces
        "app/[id]/page.tsx",  # Next.js route: [ ] are glob syntax and must match literally
        "a*b?.txt",
        'say "hi".md',  # a quote must survive TOML
    ],
)
def test_the_offered_line_lets_the_lane_change_exactly_that_file(path):
    fix = lane_owners.fix_for(config(APP, CORE), CORE, path)
    after = widened(CORE, fix.split("becomes: ", 1)[1])
    assert lane_owners.why_not(config(APP, after), after, path) is None
    assert after.owns[:2] == CORE.owns  # the lane keeps what it had
    for neighbour in ("nested/" + path, "app/i/page.tsx", "aXbY.txt"):
        if neighbour != path:
            assert lane_owners.why_not(config(APP, after), after, neighbour) is not None, neighbour


def test_a_windows_path_is_offered_with_forward_slashes():
    fix = lane_owners.fix_for(config(APP, CORE), CORE, "data\\seed.json")
    assert fix.endswith('"data/seed.json"]')


@pytest.mark.skipif(os.name != "nt", reason="the Windows file system ignores case, so ownership does too")
def test_case_is_ignored_on_windows():
    assert lane_owners.claim(config(APP, CORE), "SRC/Core/A.py").owner == "core"


# ---- the same pattern in two lanes: an error when kit.toml loads ------------------------------------


@pytest.mark.parametrize("other", ["src/**", "/src/", "/src/**", "src/**/*"])
def test_the_same_pattern_in_two_lanes_is_found(other):
    twin = Lane(name="twin", owns=["lib/**", other], scope="", resources={})
    assert lane_owners.same_pattern(config(APP, twin).lanes) == ("app", "twin", "src/**", other)


@pytest.mark.parametrize("mine, other", [("*.py", "**/*.py"), ("Dockerfile", "**/Dockerfile"), ("docs/", "**/docs/")])
def test_a_name_and_the_same_name_under_double_star_are_the_same_pattern(mine, other):
    a = Lane(name="a", owns=[mine], scope="", resources={})
    b = Lane(name="b", owns=[other], scope="", resources={})
    assert lane_owners.same_pattern([a, b]) == ("a", "b", mine, other)


@pytest.mark.parametrize("mine, other", [("src/", "src/**"), ("/main.py", "main.py")])
def test_an_anchored_pattern_and_one_at_any_depth_are_not_the_same(mine, other):
    # Review round 1: `src/` is any src folder (globs); a leading / anchors at the root.
    a = Lane(name="a", owns=[mine], scope="", resources={})
    b = Lane(name="b", owns=[other], scope="", resources={})
    assert lane_owners.same_pattern([a, b]) is None


def test_one_lane_repeating_its_own_pattern_is_not_a_tie():
    twice = Lane(name="twice", owns=["src/**", "/src/"], scope="", resources={})
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


def test_a_git_failure_listing_files_is_a_problem_not_a_traceback(monkeypatch, tmp_path):
    # Review round 1: `lanes create` runs this after the worktrees exist; a traceback would hide them.
    from kitlib import gitfiles

    def broken(root):
        raise gitfiles.GitError("git ls-files -z failed: index corrupt")

    monkeypatch.setattr(gitfiles, "tracked", broken)
    notes, problems = lane_owners.tracked_overlaps(tmp_path, config(APP, CORE))
    assert notes == [] and problems == ["files two lanes claim not checked: git ls-files -z failed: index corrupt"]


@pytest.mark.slow
def test_the_overlap_list_stays_quick_on_a_big_repository():
    # Review round 1: every tracked file is judged; 100,000 of them must not cost tens of seconds.
    import time

    lanes = [Lane(name=f"l{n}", owns=[f"pkg{n}/**", f"pkg{n}/core/**"], scope="", resources={}) for n in range(6)]
    # Review round 2: every file must overlap (`**/*.py` and a pkgN lane), or claim() never runs.
    wide = Lane(name="wide", owns=["**/*.md", "**/*.py"], scope="", resources={})
    files = [f"pkg{n % 6}/core/mod{n}/file{n}.py" for n in range(100_000)]
    start = time.perf_counter()
    notes, _ = lane_owners.overlaps(config(*lanes, wide, shared=["docs/**"]), files)
    elapsed = time.perf_counter() - start
    assert sum(int(note.split(": ")[1].split(" ")[0]) for note in notes) == len(files)
    assert elapsed < 5  # about 2 s on a Windows laptop; the margin is for slow CI runners
