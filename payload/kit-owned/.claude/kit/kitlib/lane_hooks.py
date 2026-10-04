"""What the lane hooks decide: the session-start briefing (decision 40) and edit ownership (41).

Both work out the lane from the hook input's `cwd` and read that worktree's own `kit.toml`
(decisions 36, 37); `CLAUDE_PROJECT_DIR` isn't relied on.
"""
import os
from pathlib import Path

from . import globs, lanes
from .config import ConfigMissing, find_root, load
from .protected import relative

ROUTER_COMMAND = "kit lanes status"


def router_text(cwd: Path) -> str:
    """The briefing for a session starting in cwd; empty when the kit or lanes aren't set up."""
    root = find_root(cwd)
    try:
        config = load(root)
    except ConfigMissing:
        return ""
    if not config.lanes:
        return ""
    lane = lanes.current_lane(root, config)
    if lane is None:
        names = ", ".join(item.name for item in config.lanes)
        return (
            f"Lanes: this folder is not a lane (lanes: {names}). Work here only if the user asked for it; "
            f"lane folders are listed by `{ROUTER_COMMAND}`."
        )

    settings = config.lane_settings
    lines = [f"Lane: {lane.name} (this folder is its worktree: {root})"]
    if lane.scope:
        lines.append(f"Scope: {lane.scope}")
    lines.append(f"Owns: {', '.join(lane.owns)}")
    if settings.shared_paths:
        lines.append(f"Shared with every lane: {', '.join(settings.shared_paths)}")
    if lane.resources:
        lines.append("Resources: " + ", ".join(f"{key} = {value}" for key, value in lane.resources.items()))
    branch = lanes.branch_of(root)
    lines.append(f"Branch: {branch or 'none (detached HEAD)'}")
    warnings = drift(root, config, lane, branch)
    if warnings:
        lines.append("Warnings:")
        lines += [f"- {warning}" for warning in warnings]
    lines.append(f"Stay inside the owned and shared paths; edits elsewhere ask the user. More: {ROUTER_COMMAND}.")
    return "\n".join(lines)


def drift(root: Path, config, lane, branch: str | None) -> list[str]:
    """Local-only drift checks: no fetch, so it is fast and works offline (decision 40)."""
    warnings = []
    tip = lanes.integration_tip(root, config)
    integration = config.lane_settings.integration_branch
    if branch is None:
        warnings.append("No task branch: between tasks. Start one with `kit lanes start <task>` before editing.")
    elif not branch.startswith(lane.name + "/"):
        warnings.append(f"Branch {branch!r} is not a {lane.name}/<task> branch. Check with the user before working on it.")
    if tip is None:
        warnings.append(f"Integration branch {integration!r} not found; ahead/behind unknown.")
    else:
        if branch and _merged(root, branch, tip):
            warnings.append(f"Branch {branch!r} is already merged into {tip}: start a new task instead of adding to it.")
        _, behind = lanes.ahead_behind(root, tip)
        if behind:
            warnings.append(
                f"{behind} commit(s) behind {tip} (as of the last fetch). "
                + ("`kit lanes sync` brings them in." if branch else "The next task starts from the tip.")
            )
        if _config_differs(root, tip):
            warnings.append(
                f".claude/kit.toml differs from {tip}'s copy: lane definitions may have changed. "
                "This session uses this folder's copy; the next task starts from the new one."
            )
    dirty = lanes.dirty_count(root)
    if dirty:
        warnings.append(f"{dirty} uncommitted change(s), maybe from an earlier session: look at them before new work.")
    return warnings


def _merged(root: Path, branch: str, tip: str) -> bool:
    """The branch has commits of its own and all of them are in tip.

    The branch's creation point comes from its reflog; without one (expired, or created elsewhere)
    nothing is claimed. Squash merges aren't visible locally: plan 05 asks the PR instead.
    """
    created = lanes.git(root, "reflog", "show", "--format=%H", f"refs/heads/{branch}", check=False).split()
    if not created:
        return False
    head = lanes.git(root, "rev-parse", "HEAD").strip()
    if head == created[-1]:
        return False  # no commits of its own yet
    return lanes.is_ancestor(root, "HEAD", tip)


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
    lane = lanes.current_lane(root, config)
    if lane is None:
        return None
    rel = relative(root, cwd, target, git_bash=False)
    if rel is None:
        return None  # outside the project: not a lane question
    allowed = list(lane.owns) + list(config.lane_settings.shared_paths)
    if globs.matches_any(rel, allowed):
        return None
    return (
        f"{rel} is outside lane {lane.name!r}, which owns {', '.join(lane.owns)}"
        + (f" (shared: {', '.join(config.lane_settings.shared_paths)})" if config.lane_settings.shared_paths else "")
        + ". Editing it may conflict with another lane's work. Allow only if this lane should change it."
    )
