"""Shared paths and how they're shared (decision 116): open, append or ask, with an optional steward.

No one lane owns a shared path, and every lane may add files to it. `open`: any lane changes it too
(v0.1's only kind, still what `shared_paths` means). `append`: changing or deleting a file that
existed when the task began needs a person, so one lane can't rewrite another's changelog fragment
or an applied migration. `ask`: every change needs a person. A zone's steward is the one lane that
changes it without asking. The modes are lanekeeper's `append_only` and `escalate`
(docs/survey-lanekeeper.md); no code was borrowed.
"""

from dataclasses import dataclass

from . import globs

MODES = ("open", "append", "ask")  # each stricter than the one before
_KEYS = {"paths": list, "mode": str, "steward": str}


@dataclass(frozen=True)
class Zone:
    paths: tuple
    mode: str
    steward: str | None = None


# Changelog fragments and dated health reports only ever gain files. Backlog items move to done/
# and plans gain their status and notes at each task's end, and every lane appends to the
# decisions log (until backlog decision-log-fragments), so `append` there would ask every time.
DEFAULT_ZONES = (
    Zone(("docs/changelog.d/**", "docs/health/**"), "append"),
    Zone(("docs/backlog/**", "docs/plans/**", "docs/design/decisions-log.md"), "open"),
)


def parse(entries, shared_paths: list | None, keep_defaults: bool | None = None) -> tuple:
    """The zones from `[[shared]]` and `[project] shared_paths`, then the defaults unless switched off.

    Tables add to the defaults (backlog shared-zones-keep-defaults), so a project writing one `ask`
    table keeps its shared fragments and plans. A written `shared_paths` list replaces them, as in
    v0.1; `[project] shared_defaults` (keep_defaults), when written, decides either way. A table
    repeating a default is dropped (the plan-13 template said to uncomment them).

    Raises ValueError with a message naming the table and key; stewards are checked later, against
    the lanes (check_stewards).
    """
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        raise ValueError("'shared' must be an array of tables ([[shared]])")
    # Tables first, so check_stewards' "[[shared]] #N" counts them as written.
    zones = [_zone(entry, f"[[shared]] #{number}") for number, entry in enumerate(entries, start=1)]
    if shared_paths:
        zones.append(Zone(tuple(shared_paths), "open"))
    if keep_defaults if keep_defaults is not None else shared_paths is None:
        zones.extend(DEFAULT_ZONES)
    return tuple(dict.fromkeys(zones))


def _zone(entry, where: str) -> Zone:
    if not isinstance(entry, dict):
        raise ValueError(f"{where} must be a table")
    for key, value in entry.items():
        if key not in _KEYS:
            raise ValueError(f"{where}: unknown key {key!r} (allowed: {', '.join(sorted(_KEYS))})")
        if not isinstance(value, _KEYS[key]):
            raise ValueError(f"{where}: {key!r} must be a {_KEYS[key].__name__}, not {type(value).__name__}")
    for key in ("paths", "mode"):
        if key not in entry:
            raise ValueError(f"{where}: missing required key {key!r}")
    paths = entry["paths"]
    if not paths:
        raise ValueError(f"{where}: 'paths' must list at least one glob")
    for path in paths:
        if not isinstance(path, str):
            raise ValueError(f"{where}: 'paths' must be a list of strings")
        try:
            globs.validate(path)
        except ValueError as error:
            raise ValueError(f"{where}: 'paths': {error}") from None
    mode = entry["mode"]
    if mode not in MODES:
        raise ValueError(f"{where}: 'mode' must be one of {', '.join(map(repr, MODES))}, not {mode!r}")
    steward = entry.get("steward")
    if steward is not None and mode == "open":
        # Every lane already changes an open zone freely: a steward there would mean nothing.
        raise ValueError(f"{where}: 'steward' means nothing in an open zone; use mode 'append' or 'ask'")
    return Zone(tuple(paths), mode, steward)


def check_stewards(zones, lane_names) -> None:
    # Numbered as parse() numbers them: [[shared]] tables come first, shared_paths' zone has no steward.
    for number, zone in enumerate(zones, start=1):
        if zone.steward is not None and zone.steward not in lane_names:
            raise ValueError(f"[[shared]] #{number}: steward {zone.steward!r} is not a lane")


def paths_of(zones) -> list:
    """Every shared pattern, in the order written, once: what "shared with every lane" lists."""
    return list(dict.fromkeys(path for zone in zones for path in zone.paths))


@dataclass(frozen=True)
class Match:
    mode: str
    steward: str | None  # for messages; None also when the deciding zones name different stewards
    pattern: str  # the first matching pattern of the strictest zone, for messages


class Matcher:
    """The zones of one config, compiled once."""

    def __init__(self, zones):
        self.zones = [(zone, [(pattern, globs.file_matcher([pattern])) for pattern in zone.paths]) for zone in zones]

    def find(self, path: str, lane: str | None = None) -> Match | None:
        """How path is shared for lane: by the strictest zone matching it (order in kit.toml never
        matters), leaving out the zones lane is steward of; None when no other zone matches.

        A steward skips only its own zones: any other zone matching the path still applies, so a
        stricter zone's steward never loosens a broader zone without one (review round 1).
        """
        found = []
        for zone, patterns in self.zones:
            if lane is not None and zone.steward == lane:
                continue
            pattern = next((pattern for pattern, matches in patterns if matches(path)), None)
            if pattern is not None:
                found.append((MODES.index(zone.mode), zone, pattern))
        if not found:
            return None
        strictest = max(rank for rank, _, _ in found)
        top = [(zone, pattern) for rank, zone, pattern in found if rank == strictest]
        stewards = {zone.steward for zone, _ in top}
        return Match(MODES[strictest], stewards.pop() if len(stewards) == 1 else None, top[0][1])
