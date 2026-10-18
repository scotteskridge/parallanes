"""The lane-boundary check (decision 96): a lane's change lands only in its own and the shared paths.

The ownership hook asks before an out-of-lane edit and fails open (decision 41); this check is the
backstop when the work lands, in `parallanes lanes finish`, the pre-commit hook and CI, and it fails closed.
Rules taken from lanekeeper's merge check (docs/survey-lanekeeper.md); no code was borrowed.
Paths come from kitlib.gitfiles, where a rename already counts as a change to both names and a
base that can't be diffed is an error, never a clean result.
"""

import os

from kitlib import gitfiles, globs, lane_owners, lanes
from kitlib.config import ConfigError, lanes_only
from kitlib.findings import Finding, format_findings

CHECK = "lanes"
# For a human landing a cross-lane change on purpose; an agent setting it is blocked (kitlib.commands).
# Only where the person runs the kit: CI has no override, so a PR's way through is a non-lane branch.
ALLOW_VARIABLE = "KIT_ALLOW_CROSS_LANE"
ADVICE = (
    f"To land a cross-lane change on purpose, a person uses a branch that isn't a lane's, or sets "
    f"{ALLOW_VARIABLE}=1 locally; an agent stops and asks."
)
POLICY = lane_owners.POLICY


def lanes_before(root, config, base: str | None, lane_name: str):
    """(the config whose lanes judge the change, that lane), or None when there's no such lane.

    kit.toml as it was at base, not as the change left it, so a lane that renames or drops itself (or
    widens `owns`) is judged by the lanes it started from. No base (a brand-new project) or no
    kit.toml there: the current one. Only that lane's file version is validated, so an old kit.toml
    never blocks a branch that isn't a lane's at the base.
    """
    judge = config
    text = gitfiles.show(root, base, POLICY) if base else None
    if text is not None:
        try:
            judge = lanes_only(text, lane_name)
        except ConfigError as error:  # fail closed, but say which version is wrong: not the file on disk
            where = "HEAD" if base == "HEAD" else f"commit {base[:12]}"
            detail = str(error).removeprefix(POLICY + ": ")
            raise ConfigError(f"{POLICY} at {where}: its lanes don't load, so nothing was checked: {detail}") from None
        if judge is None:
            return None
    lane = next((lane for lane in judge.lanes if lane.name == lane_name), None)
    return (judge, lane) if lane else None


def lane_for_branch(config, branch: str | None):
    """The lane whose `<lane>/<task>` branch this is, or None: other branches aren't lane work."""
    if not branch or "/" not in branch:
        return None
    name = branch.split("/", 1)[0]
    return next((lane for lane in config.lanes if lane.name == name), None)


def ci_branch() -> str | None:
    """The pull request's branch in GitHub Actions, which checks out a detached merge commit."""
    return os.environ.get("GITHUB_HEAD_REF") or None


def check(config, lane, paths) -> list[Finding]:
    findings = []
    for path in paths:
        path = globs.normalize(path)
        judged = lane_owners.judge(config, lane, path)  # the hook's rule and fix too (decision 97)
        if judged is None:
            continue
        why, fix = judged
        message = f"outside lane {lane.name!r}: {why}" + (f"; {fix.text}" if fix else "")
        findings.append(Finding(path=path, line=0, check=CHECK, message=message))
    return sorted(findings)


def listed(config, lane, paths, existing: frozenset) -> list[Finding]:
    """The shared-path changes that need a person's yes (decision 116): listed, never refused.

    The ownership hook asked for each at edit time; listing them where the work lands shows a
    reviewer what was approved, and shows one the hook missed (it fails open). existing: the paths
    that were files where the task began (existing()).
    """
    notes = []
    for path in paths:
        path = globs.normalize(path)
        if lane_owners.judge(config, lane, path) is not None:
            continue  # check() refuses it
        why = lane_owners.needs_person(config, lane, path, lambda path=path: path in existing)
        if why:
            notes.append(Finding(path=path, line=0, check=CHECK, message=f"shared, needs a person: {why}"))
    return sorted(notes)


def notes(root, config, lane, paths, base: str | None, merging: bool = False) -> list[Finding]:
    """listed() for a real change, with git asked which files existed only where a mode makes it
    matter (review round 1: a v0.1 kit.toml paid for it on every commit). A git failure isn't
    swallowed: callers fail closed, as for the rest of the check."""
    asked = lane_owners.existence_matters(config, lane, paths)
    return listed(config, lane, paths, existing(root, base, asked, merging) if asked else frozenset())


def existing(root, base: str | None, paths, merging: bool = False) -> frozenset:
    """Which paths were files where the task began: at base (where the task branch left the
    integration branch), and in a merge, also in what the merge brings in (another lane's files)."""
    found = gitfiles.existing(root, base, paths) if base else set()
    if merging:
        found |= gitfiles.existing(root, "MERGE_HEAD", paths)
    return frozenset(found)


def task_start(root, config) -> str | None:
    """Where this task branch left the integration branch: what a pre-commit or named-file check
    measures "existed" from, as `lanes finish` and CI do (decision 116). HEAD when there's no
    integration branch to measure from or git can't say (more is listed, never less); None before a
    new project's first commit."""
    if not gitfiles.has_ref(root, "HEAD"):
        return None
    try:
        tip = lanes.integration_tip(root, config)
        return gitfiles.merge_base(root, tip) if tip else "HEAD"
    except (gitfiles.GitError, lanes.LaneError):  # LaneError: git timed out or didn't start (review round 1)
        return "HEAD"


def say_listed(notes) -> str:
    count = "1 shared-path change that needs" if len(notes) == 1 else f"{len(notes)} shared-path changes that need"
    return (
        f"parallanes: {count} a person's yes, allowed and listed here for review "
        f"(the ownership hook asks for them at edit time):\n{format_findings(notes)}"
    )


def advice(config, lane, findings) -> str:
    """What to do about check()'s findings: how a cross-lane change lands, and how a kit.toml change
    does when a finding offers to widen the lane (only then: other stops never widen, review round 1).
    Judged again rather than read back from the message text, so rewording a fix can't break it."""
    fixes = (lane_owners.judge(config, lane, finding.path) for finding in findings)
    if any(judged and judged[1] and judged[1].widens for judged in fixes):
        return f"{ADVICE} To widen a lane as a finding says: {lane_owners.HOW_POLICY_LANDS}"
    return ADVICE


def allowed_by_human() -> bool:
    return os.environ.get(ALLOW_VARIABLE) == "1"
