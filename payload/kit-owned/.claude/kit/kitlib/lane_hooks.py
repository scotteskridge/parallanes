"""What the lane hooks decide: the session-start briefing (decision 40) and edit ownership (41).

Both work out the lane from the hook input's `cwd` and read that worktree's own `kit.toml`
(decisions 36, 37); `CLAUDE_PROJECT_DIR` isn't relied on.
"""

import os
from pathlib import Path

from . import gitfiles, globs, lane_boundary, lane_deps, lane_owners, lanes, session_lock, shared_zones
from .config import ConfigMissing, find_root, load
from .protected import relative

ROUTER_COMMAND = "sh .claude/kit/parallanes lanes status"


def router_text(cwd: Path) -> str:
    """The briefing for a session starting in cwd; empty when the kit or lanes aren't set up."""
    root = find_root(cwd)
    try:
        config = load(root)
    except ConfigMissing:
        return ""
    if not config.lanes:
        return ""
    lane, _, main = lanes.find_current(root, config)
    if lane is None:
        names = ", ".join(item.name for item in config.lanes)
        return (
            f"Lanes: this folder is not a lane (lanes: {names}). Work here only if the user asked for it; "
            f"lane folders are listed by `{ROUTER_COMMAND}`."
        )

    settings = config.lane_settings
    # Trial F7: in a nested lane, an agent dropped `.claude/worktrees/<lane>` from its folder and read
    # the main checkout. A lane beside the main checkout has no such trap.
    here = "; read and edit files here, not in the main checkout above it" if lanes.is_nested(main, root) else ""
    lines = [f"Lane: {lane.name} (this folder is its worktree: {root}{here})"]
    if lane.scope:
        lines.append(f"Scope: {_one_line(lane.scope)}")
    lines.append(f"Owns: {', '.join(lane.owns)}")
    shared = shared_line(settings.shared, lane.name)
    if shared:
        lines.append(shared)
    if lane.resources:
        lines.append("Resources: " + ", ".join(f"{key} = {value}" for key, value in lane.resources.items()))
    branch = lanes.branch_of(root)
    lines.append(f"Branch: {branch or 'none (detached HEAD)'}")
    warnings = drift(root, config, lane, branch, main)
    if warnings:
        lines.append("Warnings:")
        lines += [f"- {warning}" for warning in warnings]
    # One closing line, not two: the briefing stays under ~15 lines with every warning (decision 103).
    closing = "Stay inside the owned and shared paths; edits elsewhere ask the user."
    if len(config.lanes) > 1:
        # Decision 97: a broad lane (`src/**`) must not assume a nested lane's files are its own.
        closing += " A file another lane's more specific pattern matches is that lane's."
    lines.append(f"{closing} More: {ROUTER_COMMAND}.")
    return "\n".join(lines)


_SAYS = {"open": "open", "append": "adding files is free, changing one asks", "ask": "every change asks"}


def shared_line(zones, lane_name: str) -> str:
    """One briefing line for every zone, by mode (decision 116), with each steward named."""
    # A pattern in two zones is listed under the stricter mode only, the one that applies (review
    # round 1: a table making a default stricter listed the same pattern as both). The lane's own
    # stewarded zones are skipped when it is judged (Matcher.find), so they are always listed and
    # never hide another zone's mode from it (review round 2).
    strictest = {}
    for zone in zones:
        if zone.steward != lane_name:
            for path in zone.paths:
                strictest[path] = max(strictest.get(path, 0), shared_zones.MODES.index(zone.mode))
    parts = []
    for rank, mode in enumerate(shared_zones.MODES):
        named = []
        for zone in zones:
            if zone.mode == mode:
                own = zone.steward == lane_name
                paths = [path for path in zone.paths if own or strictest[path] == rank]
                whose = "this lane" if zone.steward == lane_name else f"lane {zone.steward}"
                named += [f"{path} (steward: {whose})" if zone.steward else path for path in paths]
        if named:
            parts.append(f"{_SAYS[mode]}: {', '.join(dict.fromkeys(named))}")
    return f"Shared: {'; '.join(parts)}" if parts else ""


def drift(root: Path, config, lane, branch: str | None, main: Path) -> list[str]:
    """Local-only drift checks: no fetch, so it is fast and works offline (decision 40)."""
    warnings = []
    lock = session_lock.find(main, root)
    if lock and lock.running:
        # First: the agent should tell the user before the session ends (decision 107).
        # Hedged: a reused pid can make an old lock look live (review round 1).
        warnings.append(
            f"A Claude Code session (pid {lock.pid}) holds this lane's `claude --worktree {lane.name}` lock. "
            "If that is this session, Claude Code deletes the lane's folder on exit if nothing changed, "
            "ignored files (.env, local settings) included: tell the user now, and open lanes from their "
            "folder instead."
        )
    elif lock:
        # Not `lanes remove`: it can't run inside the lane, and elsewhere it deletes the lane (review round 1).
        warnings.append(
            f"A Claude Code session lock (pid {lock.pid}, no longer running) is left on this lane. It doesn't "
            f'affect this session; clear it with `git worktree unlock "{root}"`.'
        )
    tip = lanes.integration_tip(root, config)
    integration = config.lane_settings.integration_branch
    if branch is None:
        warnings.append(
            "No task branch: between tasks. Start one with `sh .claude/kit/parallanes lanes start <task>` "
            "before editing."
        )
    elif not branch.startswith(lane.name + "/"):
        warnings.append(
            f"Branch {branch!r} is not a {lane.name}/<task> branch. Check with the user before working on it."
        )
    if tip is None:
        warnings.append(f"Integration branch {integration!r} not found; ahead/behind unknown.")
    else:
        if branch and _merged(root, branch, tip):
            warnings.append(
                f"Branch {branch!r} is already merged into {tip}: start a new task instead of adding to it."
            )
        _, behind = lanes.ahead_behind(root, tip)
        if behind:
            warnings.append(
                f"{behind} commit(s) behind {tip}"
                + (" (as of the last fetch). " if tip.startswith("origin/") else ". ")
                + (
                    "`sh .claude/kit/parallanes lanes sync` brings them in."
                    if branch
                    else "The next task starts from the tip."
                )
            )
        if _config_differs(root, tip):
            warnings.append(
                f".claude/kit.toml differs from {tip}'s copy: lane definitions may have changed. "
                "This session uses this folder's copy; the next task starts from the new one."
            )
    install = lane_deps.missing_node_modules(root, lanes.is_nested(main, root))
    if install:
        warnings.append(install)
    changed, untracked = lanes.changes(root)
    if changed:
        warnings.append(
            f"{changed} uncommitted change(s) to tracked files, maybe from an earlier session: "
            "look at them before new work."
        )
    if untracked:
        # Not unfinished work (decision 52): test runners leave reports. Only the task's own files land.
        warnings.append(
            f"{len(untracked)} untracked file(s): commit the ones that belong to your task; the rest won't land."
        )
    return warnings


def _merged(root: Path, branch: str, tip: str) -> bool:
    """The branch has commits of its own and all of them are in tip.

    "Its own" comes from the branch's reflog (newest first): a commit, amend, cherry-pick, revert or
    applied patch made since the branch was last created or reset, so work reset away or an old
    branch of the same name doesn't count, and a fresh branch fast-forwarded to a newer tip has none.
    Undoing only the last commit with a reset hides earlier ones too (no warning: the safe
    direction). Without a reflog nothing is claimed. Squash merges aren't visible locally:
    `lanes start` asks the PR (lane_merged.py).
    """
    subjects = lanes.git(root, "reflog", "show", "--format=%gs", f"refs/heads/{branch}", check=False).splitlines()
    for subject in subjects:
        if subject.startswith(OWN_WORK):
            return lanes.is_ancestor(root, "HEAD", tip)
        if subject.startswith(FRESH_START):
            return False
    return False


OWN_WORK = ("commit:", "commit (amend):", "commit (initial):", "cherry-pick:", "revert:", "am:")
FRESH_START = ("branch: Created", "branch: Reset", "reset:")


def _config_differs(root: Path, tip: str) -> bool:
    theirs = lanes.git(root, "show", f"{tip}:.claude/kit.toml", check=False)
    path = root / ".claude" / "kit.toml"
    if not theirs or not path.is_file():
        return False
    ours = path.read_text(encoding="utf-8-sig", errors="replace")
    return _lines(ours) != _lines(theirs.lstrip("﻿"))


def _lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.replace("\r\n", "\n").strip().split("\n")]


def ownership_reason(payload: dict) -> str | None:
    """Why this edit needs the user's approval, or None when it is in the lane (or not judged)."""
    tool_input = payload.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(target, str) or not target:
        return None
    cwd = Path(payload.get("cwd") or os.getcwd())
    root = find_root(cwd)
    try:
        config = load(root)
    except ConfigMissing:
        return None
    if config.lane_settings.ownership == "off" or not config.lanes:
        return None
    lane, _, main = lanes.find_current(root, config)
    if lane is None:
        return None
    rel = relative(root, cwd, target, git_bash=False)
    if rel is None:
        return _elsewhere(root, main, cwd, target, config, lane)
    judged = lane_owners.judge(config, lane, rel)  # the boundary check's rule and fix too (decision 97)
    if judged is None:
        shared = lane_owners.needs_person(config, lane, rel, lambda: _existed(root, config, rel))
        if shared is None:
            return None
        return (
            f"{rel} is shared by every lane, but {shared}. Allow if lane {lane.name!r} should change it: "
            "the commit then lists it for review rather than refusing it."
        )
    why, fix = judged
    reason = (
        f"{rel} isn't lane {lane.name!r}'s to change: {why}. Lane {lane.name!r} owns {', '.join(lane.owns)}"
        + (f" (shared: {', '.join(config.lane_settings.shared_paths)})" if config.lane_settings.shared_paths else "")
        + ". Editing it may conflict with another lane's work."
    )
    # Every stop says what approving does and doesn't do: in the trial (F8) the owner approved an
    # edit and the commit was refused anyway (review rounds 1 and 2).
    override = f"or a person sets {lane_boundary.ALLOW_VARIABLE}=1 for a local commit"
    if globs.matches_any_file(rel, [lane_owners.POLICY]):
        return f"{reason} No lane commits it: a person changes it on a branch that isn't a lane's."
    said = f" {fix.text[0].upper()}{fix.text[1:]}." if fix else ""
    if fix is None or not fix.widens:
        return (
            f"{reason} Allow only if this lane should change it; committing it then needs a branch that "
            f"isn't a lane's ({override}).{said}"
        )
    return (
        f"{reason}{said} {lane_owners.HOW_POLICY_LANDS} Approving this edit isn't enough: the commit is "
        f"refused from this lane until that change is merged and the lane is synced ({override})."
    )


def _existed(root: Path, config, rel: str) -> bool:
    """rel was a file where this task began, or comes in with a merge in progress, as the boundary
    check counts it (decision 116, review round 1). Fails open, as the hook does (decision 41): when
    git can't say, the edit counts as an addition and isn't asked about."""
    try:
        start = lane_boundary.task_start(root, config)
        merging = gitfiles.has_ref(root, "MERGE_HEAD")
        return bool(lane_boundary.existing(root, start, [rel], merging))
    except gitfiles.GitError:
        return False


def _elsewhere(root: Path, main: Path, cwd: Path, target: str, config, lane) -> str | None:
    """An edit outside this lane's folder: another lane's folder or the main checkout asks too."""
    for other in config.lanes:
        if (
            other.name != lane.name
            and relative(lanes.lane_folder(main, config, other), cwd, target, git_bash=False) is not None
        ):
            return (
                f"{target} is in the folder of lane {other.name!r}, not this lane's ({lane.name!r}). Edit "
                "files in this lane's own folder; another session may be working there."
            )
    rel = relative(main, cwd, target, git_bash=False)
    if rel is None:
        return None  # outside the repository: not a lane question
    if rel == ".git" or rel.startswith(".git/"):
        return f"{target} is the repository's git data, shared by every lane. Change it only if the user asked."
    return (
        f"{target} is in the main checkout, not this lane's folder ({root}). Edit the copy in this "
        "lane's folder instead; the main checkout may hold someone else's work."
    )


def _one_line(text: str, limit: int = 200) -> str:
    """A multi-line TOML string would break the briefing's line budget."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
