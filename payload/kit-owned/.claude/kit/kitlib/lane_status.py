"""`kit lanes status`: every lane at a glance, from local git data plus `gh` when it can (decision 43)."""
import itertools
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import globs
from .lanes import (ahead_behind, branch_of, dirty_count, integration_tip, is_registered, lane_folder,
                    main_checkout, same_path, toplevel, unpushed_count)


UNKNOWN = "PR: unknown"


@dataclass
class LaneStatus:
    name: str
    folder: Path
    state: str  # "ok", "not created", "missing"
    branch: str | None = None  # None: detached
    ahead: int = 0
    behind: int = 0
    dirty: int = 0
    unpushed: int | None = None  # None: no upstream
    pr: str = UNKNOWN
    here: bool = False


@dataclass
class Status:
    main: Path
    main_branch: str | None
    tip: str | None
    lanes: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def status(start: Path, config, offline: bool = False) -> Status:
    main = main_checkout(start)
    tip = integration_tip(main, config)
    result = Status(main=main, main_branch=branch_of(main), tip=tip)
    integration = config.lane_settings.integration_branch
    if config.lane_settings.merge_mode == "local" and result.main_branch == integration:
        # `git push . HEAD:<integration>` (plan 05) refuses while the branch is checked out (decision 38).
        result.warnings.append(
            f"local mode: the main checkout has {integration} checked out, so lanes can't fast-forward it. "
            f"Run there: git switch --detach {integration}"
        )
    top = toplevel(Path(start))
    gh = None if offline else shutil.which("gh")
    for lane in config.lanes:
        folder = lane_folder(main, config, lane)
        if not is_registered(main, folder):
            result.lanes.append(LaneStatus(lane.name, folder, "not created"))
            continue
        if not folder.is_dir():
            result.lanes.append(LaneStatus(lane.name, folder, "missing"))
            continue
        entry = LaneStatus(lane.name, folder, "ok", branch=branch_of(folder), dirty=dirty_count(folder))
        entry.here = top is not None and same_path(top, folder)
        if tip:
            entry.ahead, entry.behind = ahead_behind(folder, tip)
        if entry.branch:
            entry.unpushed = unpushed_count(folder)
            if gh:
                entry.pr = pr_state(gh, main, entry.branch)
                if entry.pr == UNKNOWN:
                    gh = None  # gh failed or hung: don't make every other lane wait for it too
        result.lanes.append(entry)
    result.notes += overlaps(config)
    return result


def pr_state(gh: str, main: Path, branch: str) -> str:
    """The newest PR for branch via `gh`, or "PR: unknown" whenever gh can't tell (decision 43)."""
    try:
        result = subprocess.run(
            [gh, "pr", "list", "--head", branch, "--state", "all", "--limit", "1", "--json", "number,state,url"],
            cwd=main, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
        if result.returncode != 0:
            return UNKNOWN
        prs = json.loads(result.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError):
        return UNKNOWN
    if not isinstance(prs, list):
        return UNKNOWN
    if not prs:
        return "PR: none"
    pr = prs[0]
    if not isinstance(pr, dict) or not isinstance(pr.get("number"), int) or not isinstance(pr.get("state"), str):
        return UNKNOWN
    return f"PR #{pr['number']} {pr['state']}"


def _base(pattern: str) -> str:
    """The literal folder a glob starts from (`src/core/**` → `src/core/`)."""
    pattern = globs.normalize(pattern).lstrip("/")
    cut = min((i for i, ch in enumerate(pattern) if ch in "*?["), default=len(pattern))
    literal = pattern[:cut]
    if cut == len(pattern):
        return literal.rstrip("/") + "/" if pattern.endswith("/") else literal
    return literal[: literal.rfind("/") + 1]


def overlaps(config) -> list[str]:
    """Lanes whose `owns` may cover the same files: allowed, but worth knowing (decision 42).

    Judged by the literal folder each glob starts from: nested folders may overlap. Cheap and
    sometimes cautious (`src/*.py` and `src/*.js` share `src/`); it is a note, never an error.
    """
    notes = []
    for a, b in itertools.combinations(config.lanes, 2):
        for p, q in itertools.product(a.owns, b.owns):
            bp, bq = _base(p), _base(q)
            if bp.startswith(bq) or bq.startswith(bp):
                notes.append(f"lanes {a.name} and {b.name} may overlap: {p} and {q}")
                break
    return notes


def format_status(result: Status) -> str:
    main = result.main_branch or "detached HEAD"
    lines = [f"Main checkout: {result.main} · {main}"]
    lines += [f"  ! {warning}" for warning in result.warnings]
    for lane in result.lanes:
        try:
            shown = Path(os.path.relpath(lane.folder, result.main)).as_posix()
        except ValueError:  # another drive on Windows
            shown = str(lane.folder)
        where = f"{lane.name} {shown}" + (" (this folder)" if lane.here else "")
        if lane.state == "not created":
            lines.append(f"{where} · not created (kit lanes create {lane.name})")
            continue
        if lane.state == "missing":
            lines.append(f"{where} · folder missing (git worktree prune, then kit lanes create {lane.name})")
            continue
        parts = [where]
        parts.append(lane.branch if lane.branch else "detached (between tasks)")
        if result.tip:
            parts.append(f"{lane.ahead} ahead, {lane.behind} behind {result.tip}")
        if lane.dirty:
            parts.append(f"{lane.dirty} uncommitted")
        if lane.branch:
            parts.append("not pushed" if lane.unpushed is None else f"{lane.unpushed} unpushed")
            parts.append(lane.pr)
        lines.append(" · ".join(parts))
    lines += [f"Note: {note}" for note in result.notes]
    return "\n".join(lines)
