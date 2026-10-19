"""What the installer offers beyond its questions (plan 16, decisions 122 and 123).

- Lanes: with the lanes profile and no `[[lanes]]` yet, a guess from the project's tracked folders
  (`kitlib/lane_suggest.py`), shown, and written into kit.toml only on a yes.
- A commit of the kit's files, then `lanes create`: only asked at a repository root that has a
  commit, is on the integration branch (lanes are made from it) and had no changes before the
  install, untracked files included. Only the paths the install wrote are staged and committed.
  It runs the pre-commit hook and never pushes; with an `origin`, lanes wait until it's pushed.

`--yes` and `--dry-run` never write lanes or commit: both are for scripts, and these are choices.
"""

import subprocess
import sys
import tomllib
from pathlib import Path

from kitlib import gitfiles, lane_suggest

from . import plan
from .values import confirm

KIT_TOML = ".claude/kit.toml"
COMMIT_MESSAGE = "Add parallanes"


def git(target: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=target, capture_output=True, text=True, encoding="utf-8")


def clean_repo_with_commit(target: Path, repo: Path | None, branch: str) -> bool:
    """Checked before anything is written: whether a commit would hold only the kit's files, on the
    branch lanes are made from (review round 1: a commit on another branch left `lanes create` failing)."""
    if repo != target:
        return False
    if git(target, "symbolic-ref", "--short", "-q", "HEAD").stdout.strip() != branch:
        return False  # another branch, or a detached HEAD
    if git(target, "rev-parse", "--verify", "-q", "HEAD").returncode != 0:
        return False
    # Every untracked file listed, whatever status.showUntrackedFiles says (review round 1).
    status = git(target, "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none")
    return status.returncode == 0 and not status.stdout.strip()


def has_origin(target: Path) -> bool:
    return git(target, "remote", "get-url", "origin").returncode == 0


def plan_lanes(
    target: Path, repo: Path | None, files: plan.FilePlan, branch: str, interactive: bool, read=input
) -> dict:
    """Show the guess and, on a yes, put the lanes into the planned or existing kit.toml.

    Returns {"added": [names], "why": reason there's no guess or "", "declined": bool}.
    """
    outcome = {"added": [], "why": "", "declined": False}
    write = next((w for w in files.writes if w.rel == KIT_TOML), None)
    current = write.data if write else (target / KIT_TOML).read_bytes()
    try:
        has_lanes = bool(tomllib.loads(current.decode("utf-8-sig")).get("lanes"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return outcome  # the settings plan reports a broken kit.toml and stops the install
    if has_lanes:
        return outcome
    if repo != target:
        outcome["why"] = "this folder isn't the root of a git repository"
        return outcome
    tracked = gitfiles.tracked(target)
    if not tracked:
        outcome["why"] = "nothing is committed or added to git yet"
        return outcome
    found, why = lane_suggest.suggest(tracked, branch)
    if not found:
        outcome["why"] = why
        return outcome
    text = lane_suggest.to_toml(found)
    print("\nLanes guessed from the project's folders:\n")
    print("  " + text.rstrip("\n").replace("\n", "\n  "))
    if not interactive:
        outcome["declined"] = True
        print("  (not added: a run without --yes or --dry-run asks; or paste them into .claude/kit.toml)")
        return outcome
    if not confirm("Add these lanes to .claude/kit.toml?", True, read):
        outcome["declined"] = True
        return outcome
    newline = b"\r\n" if b"\r\n" in current else b"\n"
    joined = current if current.endswith(b"\n") or not current else current + newline
    data = joined + newline + text.replace("\n", newline.decode()).encode("utf-8")
    if write:
        write.data = data
    else:
        files.writes.append(plan.Write(KIT_TOML, data, "replace", note="the lanes you accepted added at the end"))
    outcome["added"] = [lane.name for lane in found]
    return outcome


def offer_commit(target: Path, written: list, read=input) -> str:
    """Commit the paths this install wrote, on a yes: 'committed', 'declined', 'nothing' (asked
    nothing: a re-run that changed nothing) or 'failed' (git's output printed, the paths unstaged).
    Never `git add -A`: only what the kit wrote goes in. Runs the pre-commit hook."""
    status = git(target, "status", "--porcelain", "--untracked-files=all", "--", *written)
    if status.returncode != 0 or not status.stdout.strip():
        return "nothing"
    if not confirm("Commit the kit's files now?", True, read):
        return "declined"
    added = git(target, "add", "--", *written)
    if added.returncode == 0 and ".githooks/pre-commit" in written:
        # The kit's own copy only. Windows records no executable bit, so macOS/Linux clones couldn't run it.
        added = git(target, "add", "--chmod=+x", "--", ".githooks/pre-commit")
    # The index, not `commit -- paths` (that takes the files as on disk and drops the +x above). It
    # must hold the kit's paths alone: anything else staged meanwhile is the owner's (review round 1).
    staged = git(target, "diff", "--cached", "--name-only", "-z").stdout.split("\0")
    others = [path for path in staged if path and path not in written]
    if added.returncode == 0 and others:
        added = subprocess.CompletedProcess([], 1, "", f"other files are staged too: {', '.join(others)}\n")
    done = added if added.returncode != 0 else git(target, "commit", "-q", "-m", COMMIT_MESSAGE)
    if done.returncode != 0:
        git(target, "reset", "-q", "--", *written)  # the index as it was: the owner's, not half the kit's
        print(f"The commit failed; nothing was committed:\n{done.stdout}{done.stderr}", file=sys.stderr)
        return "failed"
    print(f"Committed the kit's files: {COMMIT_MESSAGE!r}")
    return "committed"


def after_install(target: Path, written: list, lanes: list, origin: bool, read=input) -> dict:
    """The commit offer, then (lanes, no origin) the `lanes create` one: {"committed", "created"}.
    Input closing at either keeps what was done and says so (review round 1)."""
    done = {"committed": False, "created": False}
    try:
        done["committed"] = offer_commit(target, written, read) == "committed"
    except EOFError:
        print("\nNo answer (input closed): nothing committed.")
        return done
    if done["committed"] and lanes and not origin:
        try:
            done["created"] = offer_lanes_create(target, read)
        except EOFError:
            print("\nNo answer (input closed): the lane folders weren't created.")
    return done


def offer_lanes_create(target: Path, read=input) -> bool:
    """Run `lanes create` on a yes; True when the lane folders exist."""
    if not confirm("Create the lane folders now?", True, read):
        return False
    cli = target / ".claude" / "kit" / "cli.py"
    result = subprocess.run(
        [sys.executable, str(cli), "lanes", "create"], cwd=target, capture_output=True, text=True, encoding="utf-8"
    )
    print(result.stdout.rstrip("\n"))
    if result.returncode != 0:
        print(f"lanes create failed:\n{result.stderr}", file=sys.stderr)
        return False
    return True
