"""Who owns a file that more than one lane's `owns` matches (decision 97).

Shared paths come first: every lane may change them. Otherwise the lane whose matching pattern is
most specific owns the file (`specificity`). Order in kit.toml never matters, so a split doesn't
silently depend on line order. The same pattern in two lanes is an error when kit.toml loads
(config); two different patterns can still tie on a real file, and then no lane owns it until one is
made more specific. The rule is lanekeeper's (docs/survey-lanekeeper.md), refined in review; no code
was borrowed. The ownership hook, the boundary check and the overlap lists all use it.
"""

import os
import re
from dataclasses import dataclass

from . import gitfiles, globs

POLICY = ".claude/kit.toml"
_WILDCARDS = re.compile(r"\*\*|\*|\?|\[[^\]]*\]")
# TOML basic strings forbid these raw (tab is allowed); a POSIX file name may hold them.
_CONTROL = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")


def canonical(pattern: str) -> str:
    """The pattern written out in full, so patterns that match the same files compare equal.

    globs anchors a pattern only when it has a slash before its end: `main.py` and `src/` match at
    any depth (`**/main.py`, `**/src/**`), while `/main.py` and `src/**` start at the root.
    """
    pattern = globs.normalize(pattern)
    anchored = "/" in pattern.rstrip("/")
    if pattern.endswith("/"):
        pattern += "**"
    pattern = pattern.lstrip("/")
    if not anchored:
        pattern = "**/" + pattern
    while "**/**" in pattern:
        pattern = pattern.replace("**/**", "**")
    if pattern == "**/*" or pattern.endswith("/**/*"):  # `src/**/*` is every file under src/, as `src/**` is
        pattern = pattern[:-2]
    return pattern


def specificity(pattern: str) -> tuple[int, bool, int, int, int]:
    """Larger is more specific: compared in order, the first difference decides.

    Wildcard-free segments (`src/core/**` over `src/**`); then rooted over any depth (`src/**` over
    `**/conftest.py`); then more literal characters (`src/**/*_test.py` over `src/**`); then fewer
    `**` (`src/*` over `src/**`); then fewer other wildcards. Length alone isn't used: `src/**` is
    longer than `src/*` but matches more (review round 1). A heuristic: a pattern it ranks wrongly
    in an odd case is settled by rewording it, and a tie is reported, never decided silently.
    """
    pattern = canonical(pattern)
    parts = pattern.split("/")
    literal = sum(1 for part in parts if not _WILDCARDS.search(part))
    found = _WILDCARDS.findall(pattern)
    double = found.count("**")  # inside a segment too: `src/a**` crosses folders (review round 2)
    characters = len(_WILDCARDS.sub("", pattern).replace("/", ""))
    return literal, parts[0] != "**", characters, -double, -(len(found) - double)


@dataclass(frozen=True)
class Claim:
    owner: str | None  # None: no lane claims the file, or a tie
    pattern: str | None  # the owner's most specific matching pattern
    losers: tuple = ()  # (lane, its best pattern) for the other lanes that match, most specific first
    tied: tuple = ()  # (lane, pattern) for every lane in a tie, by lane name


class Owners:
    """The rule for one config, compiled once: `lanes status` judges every tracked file with it."""

    def __init__(self, config):
        self.shared = globs.file_matcher(config.lane_settings.shared_paths)
        self.lanes = []
        for lane in config.lanes:
            ranked = sorted(lane.owns, key=specificity, reverse=True)
            self.lanes.append(
                (
                    lane.name,
                    globs.file_matcher(lane.owns),
                    [(p, specificity(p), globs.file_matcher([p])) for p in ranked],
                )
            )

    def claim(self, path: str, candidates=None) -> Claim:
        """Which lane owns path, by `owns` alone (shared paths are the caller's first question)."""
        best = []
        for name, matches, ranked in self.lanes if candidates is None else candidates:
            if matches(path):
                pattern, score = next((p, score) for p, score, one in ranked if one(path))
                best.append((score, name, pattern))
        if not best:
            return Claim(None, None)
        top = max(score for score, _, _ in best)
        winners = sorted((name, pattern) for score, name, pattern in best if score == top)
        if len(winners) > 1:
            return Claim(None, None, tied=tuple(winners))
        losers = tuple((name, pattern) for score, name, pattern in sorted(best, reverse=True) if score != top)
        return Claim(winners[0][0], winners[0][1], losers)

    def overlapping(self, path: str) -> list:
        """The lanes that match path, when it isn't shared and more than one does; else []."""
        if self.shared(path):
            return []
        matching = [entry for entry in self.lanes if entry[1](path)]
        return matching if len(matching) > 1 else []


def claim(config, path: str) -> Claim:
    return Owners(config).claim(path)


@dataclass(frozen=True)
class Fix:
    text: str  # a clause to follow the reason, e.g. after "; "
    widens: bool  # True: it's a kit.toml change, so the stop also says how one lands (HOW_POLICY_LANDS)


# kit.toml belongs to no lane, and a lane's change is judged by the kit.toml it started from
# (lane_boundary.lanes_before), so a fix that widens a lane can't ride in that lane's own branch.
HOW_POLICY_LANDS = (
    f"{POLICY} belongs to no lane: a person commits a change to it on a branch that isn't a lane's "
    "and merges it, then `sh .claude/kit/parallanes lanes sync` brings it into the lane."
)


def judge(config, lane, path: str) -> tuple[str, Fix | None] | None:
    """(why lane may not change path, the change that would let it), or None when it may.

    The ownership hook and the boundary check both ask this, so they give the same reason and fix.
    A file no lane owns gets the one pattern to add, matching that file alone so the boundary widens
    only as far as the task needs; the addition, not a whole `owns` line, because the lane's copy of
    kit.toml may be older than the integration branch's (review round 1). A file another lane owns
    gets no widening: taking it would move the boundary under that lane. A tie already says how to
    settle it. The policy itself is no lane's: a lane owning it could widen itself.
    """
    if globs.matches_any_file(path, [POLICY]):
        return "the lane policy belongs to no lane", None
    owners = Owners(config)
    if owners.shared(path):
        return None
    found = owners.claim(path)
    if found.owner == lane.name:
        return None
    if found.tied:
        names = " and ".join(repr(name) for name, _ in found.tied)
        patterns = ", ".join(pattern for _, pattern in found.tied)
        return f"lanes {names} claim it equally ({patterns}); make one pattern in {POLICY} more specific", None
    if found.owner is not None:
        mine = dict(found.losers).get(lane.name)
        why = (
            f"owned by lane {found.owner!r}"
            if mine is None
            else f"{mine} matches it, but lane {found.owner!r} owns it: {found.pattern} is more specific"
        )
        return why, Fix("make this change from that lane instead", widens=False)
    addition = _toml_string(literal(path))
    return "no lane owns it", Fix(f"add {addition} to the owns of lane {lane.name!r} in {POLICY}", widens=True)


def literal(path: str) -> str:
    """A pattern matching path alone: wildcards bracketed (`[id]` is a Next.js folder name, not a
    class), and a bare name anchored, since `.gitignore` alone would match every nested one (globs)."""
    path = globs.normalize(path)
    pattern = re.sub(r"[*?\[]", lambda found: f"[{found.group()}]", path)
    return pattern if "/" in pattern else "/" + pattern


def _toml_string(text: str) -> str:
    """A TOML basic string, with quotes, backslashes and control characters escaped."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    escaped = _CONTROL.sub(lambda found: f"\\u{ord(found.group()):04x}", escaped)
    return f'"{escaped}"'


def same_pattern(lanes) -> tuple[str, str, str, str] | None:
    """(lane, other lane, its pattern, the other's) for the first pattern two lanes both list."""
    seen = {}
    for lane in lanes:
        for pattern in lane.owns:
            key = canonical(pattern)
            key = key.lower() if os.name == "nt" else key  # matching ignores case there (globs)
            first = seen.setdefault(key, (lane.name, pattern))
            if first[0] != lane.name:
                return first[0], lane.name, first[1], pattern
    return None


def overlaps(config, paths) -> tuple[list[str], list[str]]:
    """(notes, problems) about the files more than one lane claims, grouped by outcome.

    A note says which lane wins; a problem is a tie, which no lane owns until someone decides.
    """
    owners = Owners(config)
    groups: dict = {}
    for path in paths:
        matching = owners.overlapping(path)
        if matching:
            groups.setdefault(owners.claim(path, matching), []).append(path)
    notes, problems = [], []
    for found, grouped in groups.items():
        count = f"{len(grouped)} file{'' if len(grouped) == 1 else 's'}"
        example = f"e.g. {min(grouped)}"
        if found.tied:
            who = " and ".join(f"{pattern} ({name})" for name, pattern in found.tied)
            settle = f"no lane owns it until one pattern in {POLICY} is more specific"
            problems.append(f"{who} claim {count} equally, {example}: {settle}")
        else:
            others = ", ".join(f"{pattern} ({name})" for name, pattern in found.losers)
            notes.append(f"{found.pattern} ({found.owner}) wins over {others}: {count}, {example}")
    return sorted(notes), sorted(problems)


def tracked_overlaps(root, config) -> tuple[list[str], list[str]]:
    """overlaps() for the files git tracks in root; a git failure is a problem line, not a traceback."""
    if len(config.lanes) < 2:
        return [], []
    try:
        paths = gitfiles.tracked(root)
    except gitfiles.GitError as error:
        return [], [f"files two lanes claim not checked: {error}"]
    return overlaps(config, paths)
