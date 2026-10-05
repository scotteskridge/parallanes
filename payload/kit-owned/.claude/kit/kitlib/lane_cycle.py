"""`kit lanes start / sync / finish`: one task's cycle inside a lane (decisions 11, 12, 46-51).

Each command runs only in a lane folder and acts on that lane's worktree. It returns short lines an
agent can quote; a refusal is a LaneError whose message says why and what to do next.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from kitlib import lane_merged, lanes
from kitlib.lanes import LaneError

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")  # the lane-name pattern, at most 50 characters
IN_PROGRESS = {"rebase-merge": "rebase", "rebase-apply": "rebase", "MERGE_HEAD": "merge",
               "CHERRY_PICK_HEAD": "cherry-pick"}


class Unfinished(LaneError):
    """The work didn't land: tests failed, or the branch is pushed but no PR was opened (exit 1)."""


# ---- the three commands --------------------------------------------------------------------------

def start(folder: Path, config, task: str, abandon: bool = False) -> list[str]:
    lane, top, _ = _here(folder, config)
    if not SLUG.match(task):
        raise LaneError(f"task {task!r}: use lowercase letters, digits and hyphens, at most 50 characters (e.g. fix-login)")
    _nothing_in_progress(top)
    _clean(top)
    new = f"{lane.name}/{task}"
    if _exists(top, f"refs/heads/{new}"):
        raise LaneError(f"branch {new} already exists: pick another task name")
    current = lanes.branch_of(top)
    if current is not None:
        _check_task_branch(current, lane)
    tip = _fetch_tip(top, config)
    lines = []
    if current is not None:
        done, why = lane_merged.merged(top, config, current, tip)
        if not done and not abandon:
            raise LaneError(f"{why}. To drop {current} on purpose: kit lanes start {task} --abandon")
        sha = _rev(top, "HEAD")
        _git(top, "switch", "-q", "--detach", tip)
        _git(top, "branch", "-q", "-D", current)  # proved merged above, or abandoned on request
        lines.append(f"Deleted {current}: {why}." if done
                     else f"Abandoned {current} at {sha}. To get it back: git branch {current} {sha}")
    # --no-track: otherwise git makes origin/<integration> the upstream and "pushed?" checks lie (decision 47).
    _git(top, "switch", "-q", "--no-track", "-c", new, tip)
    lines.append(f"On {new}, from {tip} ({_rev(top, 'HEAD')[:12]}).")
    leftovers = [name for name in _git(top, "for-each-ref", "--format=%(refname:short)", f"refs/heads/{lane.name}/").split()
                 if name != new]
    if leftovers:
        lines.append(f"Other {lane.name}/ branches, left alone: {', '.join(leftovers)}")
    return lines


def sync(folder: Path, config) -> list[str]:
    lane, top, _ = _here(folder, config)
    _nothing_in_progress(top)
    branch = _task_branch(top, lane)
    _clean(top)
    return _bring_in(top, branch, _fetch_tip(top, config))


def finish(folder: Path, config, title: str | None = None, body_file: str | None = None) -> list[str]:
    lane, top, main = _here(folder, config)
    _nothing_in_progress(top)
    branch = _task_branch(top, lane)
    _clean(top)
    command = config.project.get("test_command", "").strip()
    if not command:
        raise LaneError("no test_command in .claude/kit.toml: finish runs the tests before anything lands, so set it first")
    body = os.path.abspath(body_file) if body_file else None
    if body and not Path(body).is_file():
        raise LaneError(f"body file {body_file} not found")
    local = config.lane_settings.merge_mode == "local"
    integration = config.lane_settings.integration_branch
    if local:
        _main_not_holding(main, integration)
    tip = _fetch_tip(top, config)
    if lanes.ahead_behind(top, tip)[0] == 0:
        raise LaneError(f"nothing to finish: {branch} has no commits that aren't in {tip}")
    lines = _bring_in(top, branch, tip)  # so the tests run on what will actually land
    _run_tests(top, command)
    if local:
        return lines + _land_locally(top, main, config, branch, command)
    return lines + _open_pr(top, integration, branch, tip, title, body)


# ---- steps ---------------------------------------------------------------------------------------

def _bring_in(top: Path, branch: str, tip: str) -> list[str]:
    """Rebase a branch that was never pushed; merge one that was, so nothing under review is rewritten."""
    behind = lanes.ahead_behind(top, tip)[1]
    if not behind:
        return [f"{branch} is up to date with {tip}."]
    pushed = _exists(top, f"refs/remotes/origin/{branch}")
    verb = "merge" if pushed else "rebase"
    result = _run(top, "merge", "-q", "--no-edit", tip) if pushed else _run(top, "rebase", "-q", tip)
    if result.returncode != 0:
        conflicts = _git(top, "diff", "--name-only", "--diff-filter=U").split()
        if not conflicts:
            raise LaneError(f"git {verb} {tip} failed: {(result.stderr or result.stdout).strip()}")
        # Left in progress on purpose: resolving the conflict is the work (decision 48).
        raise LaneError(
            f"conflict while bringing {tip} into {branch} ({verb}): {', '.join(conflicts)}. "
            f"Fix those files, `git add` them, then `git {verb} --continue`; to give up instead: "
            f"`git {verb} --abort`."
        )
    return [f"{'Merged' if pushed else 'Rebased onto'} {tip}: {behind} new commit(s)."]


def _run_tests(top: Path, command: str) -> None:
    print(f"Running the tests: {command}", flush=True)
    sys.stderr.flush()
    try:
        # Through the shell: real test commands chain (`npm test && ...`); the value comes from the
        # committed, protected kit.toml (decision 50). Output streams straight to the terminal.
        result = subprocess.run(command, shell=True, cwd=top)
    except OSError as error:
        raise Unfinished(f"can't run the tests ({error}): nothing was pushed or merged") from None
    if result.returncode != 0:
        raise Unfinished(
            f"tests failed (exit {result.returncode}): nothing was pushed or merged. "
            "Fix them, commit, and run `kit lanes finish` again."
        )


def _land_locally(top: Path, main: Path, config, branch: str, command: str) -> list[str]:
    integration = config.lane_settings.integration_branch
    lines = []
    for attempt in (1, 2):
        pushed = _run(top, "push", "-q", ".", f"HEAD:refs/heads/{integration}")
        if pushed.returncode == 0:
            break
        if attempt == 2:
            raise LaneError(f"couldn't fast-forward {integration} twice: {pushed.stderr.strip()}")
        _main_not_holding(main, integration)
        lines.append(f"{integration} moved while the tests ran (another lane finished): syncing and testing again.")
        lines += _bring_in(top, branch, _fetch_tip(top, config))
        _run_tests(top, command)
    sha = _rev(top, "HEAD")
    _git(top, "switch", "-q", "--detach", integration)
    _git(top, "branch", "-q", "-d", branch)  # -d: git itself confirms it's merged
    lines.append(f"{integration} fast-forwarded to {sha[:12]}; {branch} deleted. Between tasks: next, kit lanes start <task>.")
    return lines


def _open_pr(top: Path, integration: str, branch: str, tip: str, title: str | None, body: str | None) -> list[str]:
    pushed = _run(top, "push", "-q", "-u", "origin", branch)  # never --force (decision 48)
    if pushed.returncode != 0:
        raise LaneError(f"git push failed: {pushed.stderr.strip()}")
    lines = [f"Pushed {branch} to origin."]
    remote = _git(top, "remote", "get-url", "origin").strip()
    where = compare_url(remote, integration, branch)
    by_hand = f"open the PR yourself: {where}" if where else f"open the PR yourself ({branch} into {integration})"
    prs, error = lane_merged.pull_requests(top, branch, "open")
    if error:
        raise Unfinished(f"{branch} is pushed, but {error}; {by_hand}")
    if prs:
        return lines + [f"PR #{prs[0]['number']} is already open and now has these commits: {prs[0].get('url', '')}"]
    subjects = _git(top, "log", "--reverse", "--format=%s", f"{tip}..HEAD").splitlines()
    args = [shutil.which("gh") or "gh", "pr", "create", "--base", integration, "--head", branch,
            "--title", title or subjects[0]]
    if body:
        args += ["--body-file", body]
    else:
        args += ["--body", "Commits:\n" + "\n".join(f"- {s}" for s in subjects) + "\n\nOpened by `kit lanes finish`."]
    try:
        created = subprocess.run(args, cwd=top, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise Unfinished(f"{branch} is pushed, but gh pr create couldn't run ({error}); {by_hand}") from None
    if created.returncode != 0:
        raise Unfinished(f"{branch} is pushed, but gh pr create failed ({created.stderr.strip()[:300]}); {by_hand}")
    return lines + [f"Opened {created.stdout.strip()}"]


def compare_url(remote: str, base: str, head: str) -> str | None:
    """GitHub's "open a pull request" page for head, or None for any other host."""
    match = re.match(r"^(?:git@github\.com:|(?:https|ssh)://(?:git@)?github\.com/)([^/]+)/(.+?)(?:\.git)?/?$", remote.strip())
    if not match:
        return None
    return f"https://github.com/{match[1]}/{match[2]}/compare/{base}...{head}?expand=1"


# ---- checks and git helpers ----------------------------------------------------------------------

def _here(folder: Path, config):
    lane, top, main = lanes.find_current(Path(folder), config)
    if lane is None:
        names = ", ".join(lane.name for lane in config.lanes) or "none"
        raise LaneError(
            f"not a lane folder: run this inside {config.lane_settings.worktree_root}/<lane> (lanes: {names})"
        )
    return lane, top, main


def _nothing_in_progress(top: Path) -> None:
    paths = _git(top, "rev-parse", "--path-format=absolute", *[arg for name in IN_PROGRESS for arg in ("--git-path", name)])
    for name, path in zip(IN_PROGRESS, paths.splitlines()):
        if Path(path).exists():
            kind = IN_PROGRESS[name]
            raise LaneError(
                f"a {kind} is in progress here: finish it (`git {kind} --continue`) or undo it (`git {kind} --abort`) first"
            )


def _clean(top: Path) -> None:
    dirty = lanes.dirty_count(top)
    if dirty:
        raise LaneError(f"{dirty} uncommitted change(s) in this lane: commit or stash them first")


def _task_branch(top: Path, lane) -> str:
    branch = lanes.branch_of(top)
    if branch is None:
        raise LaneError("between tasks: no task branch here. Start one with: kit lanes start <task>")
    _check_task_branch(branch, lane)
    return branch


def _check_task_branch(branch: str, lane) -> None:
    if not branch.startswith(lane.name + "/"):
        raise LaneError(f"{branch!r} isn't a {lane.name}/<task> branch, so the kit leaves it alone: switch away from it first")


def _main_not_holding(main: Path, integration: str) -> None:
    if lanes.branch_of(main) == integration:
        raise LaneError(
            f"local mode: the main checkout has {integration} checked out, so it can't be fast-forwarded. "
            f"Run there: git switch --detach {integration}"
        )


def _fetch_tip(top: Path, config) -> str:
    """The integration tip, fetched first in PR mode (local mode works offline)."""
    if config.lane_settings.merge_mode == "pr" and "origin" in _git(top, "remote").split():
        _git(top, "fetch", "-q", "origin")
    tip = lanes.integration_tip(top, config)
    if tip is None:
        raise LaneError(f"integration branch {config.lane_settings.integration_branch!r} not found (locally or on origin)")
    return tip


def _exists(top: Path, ref: str) -> bool:
    return bool(_git(top, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}", check=False).strip())


def _rev(top: Path, ref: str) -> str:
    return _git(top, "rev-parse", ref).strip()


def _git(top: Path, *args: str, check: bool = True) -> str:
    return lanes.git(top, *args, check=check)


def _run(top: Path, *args: str) -> subprocess.CompletedProcess:
    """git with its exit code, for the steps whose failure has its own message."""
    try:
        return subprocess.run(["git", *args], cwd=top, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=300)
    except (OSError, subprocess.SubprocessError) as error:
        raise LaneError(f"git {' '.join(args)}: {error}") from None
