"""Who owns a file that more than one lane's `owns` matches (decision 97).

Shared paths come first: every lane may change them. Otherwise the lane whose matching pattern is
most specific owns the file: most wildcard-free segments, then the longer pattern. Order in kit.toml
never matters, so a split doesn't silently depend on line order. The same pattern in two lanes is an
error when kit.toml loads (config); two different patterns can still tie on a real file, and then no
lane owns it until one is made more specific. The rule is lanekeeper's (docs/survey-lanekeeper.md);
no code was borrowed. The ownership hook, the boundary check and the overlap report all use it.
"""

import os
from dataclasses import dataclass

from . import globs

POLICY = ".claude/kit.toml"


def _canonical(pattern: str) -> str:
    """The form a pattern is compared and scored in: `/src/` and `src/**` match the same files."""
    pattern = globs.normalize(pattern).lstrip("/")
    return pattern + "**" if pattern.endswith("/") else pattern


def specificity(pattern: str) -> tuple[int, int]:
    """(wildcard-free segments, length): the larger, the more specific."""
    pattern = _canonical(pattern)
    literal = [part for part in pattern.split("/") if part and not globs.WILDCARD.search(part)]
    return len(literal), len(pattern)


@dataclass(frozen=True)
class Claim:
    owner: str | None  # None: no lane claims the file, or a tie
    pattern: str | None  # the owner's most specific matching pattern
    losers: tuple = ()  # (lane, its best pattern) for the other lanes that match
    tied: tuple = ()  # (lane, pattern) for every lane in a tie, by lane name


def claim(config, path: str) -> Claim:
    """Which lane owns path, by `owns` alone (shared paths are the caller's first question)."""
    best = []
    for lane in config.lanes:
        matching = [pattern for pattern in lane.owns if globs.matches_any_file(path, [pattern])]
        if matching:
            pattern = max(matching, key=specificity)
            best.append((specificity(pattern), lane.name, pattern))
    if not best:
        return Claim(None, None)
    top = max(score for score, _, _ in best)
    winners = sorted((name, pattern) for score, name, pattern in best if score == top)
    if len(winners) > 1:
        return Claim(None, None, tied=tuple(winners))
    losers = tuple((name, pattern) for score, name, pattern in sorted(best, reverse=True) if score != top)
    return Claim(winners[0][0], winners[0][1], losers)


def is_shared(config, path: str) -> bool:
    return globs.matches_any_file(path, config.lane_settings.shared_paths)


def why_not(config, lane, path: str) -> str | None:
    """Why lane may not change path, or None when it may (shared, or the lane owns it)."""
    if is_shared(config, path):
        return None
    found = claim(config, path)
    if found.owner == lane.name:
        return None
    if found.tied:
        names = " and ".join(repr(name) for name, _ in found.tied)
        patterns = ", ".join(pattern for _, pattern in found.tied)
        return f"lanes {names} claim it equally ({patterns}); make one pattern in {POLICY} more specific"
    if found.owner is None:
        return "no lane owns it"
    mine = dict(found.losers).get(lane.name)
    if mine is None:
        return f"owned by lane {found.owner!r}"
    return f"owned by lane {found.owner!r} ({found.pattern} is more specific than {mine})"


def same_pattern(lanes) -> tuple[str, str, str, str] | None:
    """(lane, other lane, its pattern, the other's) for the first pattern two lanes both list."""
    seen = {}
    for lane in lanes:
        for pattern in lane.owns:
            key = _canonical(pattern)
            key = key.lower() if os.name == "nt" else key  # matching ignores case there (globs)
            first = seen.setdefault(key, (lane.name, pattern))
            if first[0] != lane.name:
                return first[0], lane.name, first[1], pattern
    return None


def overlaps(config, files) -> tuple[list[str], list[str]]:
    """(notes, problems) about the files more than one lane claims, grouped by outcome.

    A note says which lane wins; a problem is a tie, which no lane owns until someone decides.
    """
    groups: dict = {}
    for path in files:
        if is_shared(config, path):
            continue
        found = claim(config, path)
        if found.losers or found.tied:
            groups.setdefault(found, []).append(path)
    notes, problems = [], []
    for found, paths in groups.items():
        files = f"{len(paths)} file{'' if len(paths) == 1 else 's'}"
        example = f"e.g. {sorted(paths)[0]}"
        if found.tied:
            who = " and ".join(f"{pattern} ({name})" for name, pattern in found.tied)
            settle = f"no lane owns it until one pattern in {POLICY} is more specific"
            problems.append(f"{who} claim {files} equally, {example}: {settle}")
        else:
            others = ", ".join(f"{pattern} ({name})" for name, pattern in found.losers)
            notes.append(f"{found.pattern} ({found.owner}) wins over {others}: {files}, {example}")
    return sorted(notes), sorted(problems)
