"""Lanes: one git worktree per lane, found from the config and git alone (decisions 11, 35-39, 42, 43).

No state file: a folder is a lane when its git top level is `<main checkout>/<worktree_root>/<name>`,
so nothing can go stale. The main checkout is the folder that holds the repository's common `.git`.
"""
import os
import shutil
import subprocess
from pathlib import Path

from .settings import SettingsError, Style, read_json, style_of, write_json

LOCAL_SETTINGS_REL = Path(".claude") / "settings.local.json"
# The main checkout's instruction files. Claude Code loads every CLAUDE.md from the session folder up
# to the filesystem root, so a nested lane would also read these (decision 35).
INSTRUCTION_FILES = ("CLAUDE.md", "AGENTS.md", ".claude/CLAUDE.md")


class LaneError(Exception):
    """A lanes command can't go ahead; the message says why and what to do."""


class PartialCreate(LaneError):
    """Some lanes failed; lines still says what happened to every lane."""

    def __init__(self, message: str, lines: list[str]):
        super().__init__(message)
        self.lines = lines


def git(folder: Path, *args: str, check: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=folder, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise LaneError(f"git {' '.join(args)}: {error}") from None
    if check and result.returncode != 0:
        raise LaneError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout if result.returncode == 0 else ""


def same_path(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def toplevel(folder: Path) -> Path | None:
    out = git(folder, "rev-parse", "--show-toplevel", check=False).strip()
    return Path(out) if out else None


def main_checkout(folder: Path) -> Path:
    """The main working tree, found from any folder of the repository (a lane included).

    In the main checkout it is the git top level. From a linked worktree, git lists it first in
    `worktree list`, except when the repository was set up with a separate git dir (git then lists
    the git dir itself), which can't be traced back from a lane: that case is an error, not a guess.
    """
    git_dir = git(folder, "rev-parse", "--path-format=absolute", "--git-dir").strip()
    common = git(folder, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    if same_path(Path(git_dir), Path(common)):
        top = toplevel(folder)
        if top is None:
            raise LaneError("this repository has no working tree (it is bare): lanes need one")
        return top
    first = git(folder, "worktree", "list", "--porcelain", "-z").split("\0\0")[0].split("\0")
    main = Path(first[0][len("worktree "):]) if first[0].startswith("worktree ") else None
    if main is None or "bare" in first or same_path(main, Path(common)):
        raise LaneError(
            "can't find the main checkout from this worktree (the repository is bare or uses a separate "
            "git dir); lanes need a normal checkout"
        )
    return main


def worktree_root(main: Path, config) -> Path:
    name = config.project.get("name") or main.name
    root = config.lane_settings.worktree_root.replace("{project}", name)
    return Path(os.path.normpath(main / root))


def lane_folder(main: Path, config, lane) -> Path:
    return worktree_root(main, config) / lane.name


def is_nested(main: Path, folder: Path) -> bool:
    try:
        Path(os.path.normcase(os.path.abspath(folder))).relative_to(os.path.normcase(os.path.abspath(main)))
    except ValueError:
        return False
    return True


def current_lane(folder: Path, config):
    """The lane whose worktree contains folder, or None (the main checkout, or any other folder)."""
    top = toplevel(Path(folder))
    if top is None:
        return None
    main = main_checkout(top)
    return next((lane for lane in config.lanes if same_path(top, lane_folder(main, config, lane))), None)


def find_lane(config, name: str):
    for lane in config.lanes:
        if lane.name == name:
            return lane
    known = ", ".join(lane.name for lane in config.lanes) or "none"
    raise LaneError(f"no lane named {name!r} in .claude/kit.toml (lanes: {known})")


def integration_tip(folder: Path, config) -> str | None:
    """Where finished work lands: PR mode prefers `origin/<integration>`, local mode the local
    branch (ARCHITECTURE §6); each falls back to the other. None if neither exists.

    No fetch: everything here works offline (decision 39).
    """
    branch = config.lane_settings.integration_branch
    refs = (f"origin/{branch}", branch)
    if config.lane_settings.merge_mode == "local":
        refs = refs[::-1]
    for ref in refs:
        if git(folder, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}", check=False).strip():
            return ref
    return None


def is_ancestor(folder: Path, commit: str, of: str) -> bool:
    try:
        result = subprocess.run(["git", "merge-base", "--is-ancestor", commit, of], cwd=folder, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise LaneError(f"git merge-base: {error}") from None
    if result.returncode not in (0, 1):
        raise LaneError(f"git merge-base --is-ancestor failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    return result.returncode == 0


def registered_worktrees(main: Path) -> list[Path]:
    out = git(main, "worktree", "list", "--porcelain", "-z")
    return [Path(entry[len("worktree "):]) for entry in out.split("\0") if entry.startswith("worktree ")]


def is_registered(main: Path, folder: Path) -> bool:
    return any(same_path(path, folder) for path in registered_worktrees(main))


# ---- create ------------------------------------------------------------------------------------

def _selected(config, names) -> list:
    if not config.lanes:
        raise LaneError("no lanes defined: add [[lanes]] tables to .claude/kit.toml")
    return [find_lane(config, name) for name in names] if names else list(config.lanes)


def create(start: Path, config, names=(), dry_run: bool = False) -> list[str]:
    """Create the named lanes (all when none are named). Returns one line per lane."""
    main = main_checkout(start)
    selected = _selected(config, names)
    tip = integration_tip(main, config)
    if tip is None:
        branch = config.lane_settings.integration_branch
        raise LaneError(f"integration branch {branch!r} not found (neither origin/{branch} nor {branch})")
    root = worktree_root(main, config)
    if is_nested(main, root):
        rel = Path(os.path.relpath(root, main)).as_posix()
        # A folder that isn't ignored shows up as an untracked nested repository in every `git status`.
        if _not_ignored(main, f"{rel}/x"):
            raise LaneError(
                f"{rel}/ is not gitignored. Add this line to .gitignore, commit it, then run this again:\n"
                f"  {rel}/"
            )

    lines, todo = [], []
    for lane in selected:
        folder = lane_folder(main, config, lane)
        if folder.exists():
            if is_registered(main, folder):
                lines.append(f"{lane.name}: already created at {folder}")
                todo.append((lane, folder, False))  # re-run the steps a failed run may have missed
                continue
            raise LaneError(f"{lane.name}: {folder} exists but is not this lane's worktree; move it away first")
        todo.append((lane, folder, True))
        lines.append(f"{lane.name}: {'would create' if dry_run else 'created'} {folder}, detached at {tip}")
    if dry_run:
        return lines

    include = _worktreeinclude_files(main, root)
    errors = []
    for lane, folder, new in todo:
        try:
            if new:
                git(main, "worktree", "add", "--detach", str(folder), tip)
                _copy(main, folder, include)
            if is_nested(main, folder):
                exclude_main_instructions(main, folder)
        except LaneError as error:
            errors.append(f"{lane.name}: {error}")
    if errors:
        # Every lane is attempted and reported, so a rerun after a fix finishes the job.
        raise PartialCreate("\n".join(errors), lines)
    return lines


def _copy(main: Path, folder: Path, include: list[str]) -> None:
    for rel in include:
        target = folder / rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(main / rel, target)
        except OSError as error:
            raise LaneError(f"couldn't copy {rel} into the lane: {error}") from None


def _not_ignored(main: Path, rel: str) -> bool:
    try:
        result = subprocess.run(["git", "check-ignore", "-q", rel], cwd=main, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise LaneError(f"git check-ignore: {error}") from None
    if result.returncode not in (0, 1):
        raise LaneError(f"git check-ignore failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    return result.returncode == 1


def _worktreeinclude_files(main: Path, root: Path) -> list[str]:
    """Files that match `.worktreeinclude` and are gitignored, as Claude Code copies them.

    git does the matching, so it is exactly gitignore syntax. Other lanes' folders are skipped.
    """
    if not (main / ".worktreeinclude").is_file():
        return []
    args = ["ls-files", "-z", "--others", "--ignored", "--exclude-from=.worktreeinclude"]
    if is_nested(main, root):
        args += ["--", ".", f":(exclude){Path(os.path.relpath(root, main)).as_posix()}"]
    listed = [name for name in git(main, *args).split("\0") if name]
    if not listed:
        return []
    result = subprocess.run(
        ["git", "check-ignore", "-z", "--stdin"], cwd=main, input="\0".join(listed).encode("utf-8"),
        capture_output=True, timeout=60,
    )
    if result.returncode not in (0, 1):
        raise LaneError(f"git check-ignore failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    ignored = {name for name in result.stdout.decode("utf-8", "replace").split("\0") if name}
    return [name for name in listed if name in ignored and (main / name).is_file()]


def exclude_main_instructions(main: Path, folder: Path) -> None:
    """Add the main checkout's instruction files to the lane's claudeMdExcludes (decision 35).

    `settings.local.json` is gitignored and specific to this machine, the right home for absolute
    paths. Other keys and the file's formatting are kept; an unreadable file is left alone.
    """
    path = folder / LOCAL_SETTINGS_REL
    what = f"{folder.name}/{LOCAL_SETTINGS_REL.as_posix()}"
    try:
        data = read_json(path, what)
    except SettingsError as error:
        raise LaneError(f"{error}. The lane was created; add claudeMdExcludes by hand (docs/ai/parallel-lanes.md)") from None
    excludes = data.get("claudeMdExcludes", [])
    if not isinstance(excludes, list):
        raise LaneError(f"{what}: 'claudeMdExcludes' must be a list; left untouched")
    added = [entry for entry in main_instruction_excludes(main) if entry not in excludes]
    if added:
        data["claudeMdExcludes"] = excludes + added
        try:
            write_json(path, data, style_of(path) if path.is_file() else Style())
        except OSError as error:
            raise LaneError(f"{what}: can't write it: {error}") from None


def main_instruction_excludes(main: Path) -> list[str]:
    return [Path(os.path.realpath(main / name)).as_posix() for name in INSTRUCTION_FILES]


# ---- remove ------------------------------------------------------------------------------------

def remove(start: Path, config, name: str, force: bool = False) -> str:
    lane = find_lane(config, name)
    main = main_checkout(start)
    folder = lane_folder(main, config, lane)
    if not is_registered(main, folder):
        raise LaneError(f"{name}: not created ({folder} is not a worktree of this repository)")
    top = toplevel(Path(start))
    if top is not None and same_path(top, folder):
        raise LaneError(f"{name}: can't remove the lane this command runs in; run it from another folder")
    changes = git(folder, "status", "--porcelain").splitlines()
    if changes:
        raise LaneError(f"{name}: {len(changes)} uncommitted change(s) in {folder}; commit or discard them first")
    if not force:
        # git ignores ignored files, but they can hold work: a lane's .env, its local settings.
        kept = ignored_work(main, folder)
        if kept:
            shown = ", ".join(kept[:10]) + (f" and {len(kept) - 10} more" if len(kept) > 10 else "")
            raise LaneError(
                f"{name}: removing {folder} would delete ignored files: {shown}. "
                "Save what you need, then run again with --force"
            )
    git(main, "worktree", "remove", *(["--force"] if force else []), str(folder))
    return f"{name}: removed {folder}"


def ignored_work(main: Path, folder: Path) -> list[str]:
    """Ignored files and folders in the lane, except those `create` put there and nobody changed."""
    out = git(folder, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory")
    lost = []
    for rel in (name for name in out.split("\0") if name):
        mine, original = folder / rel, main / rel
        if rel == LOCAL_SETTINGS_REL.as_posix() and _only_our_excludes(main, mine, original):
            continue
        if mine.is_file() and original.is_file() and mine.read_bytes() == original.read_bytes():
            continue  # copied from .worktreeinclude and unchanged
        lost.append(rel)
    return lost


def _only_our_excludes(main: Path, mine: Path, original: Path) -> bool:
    """The lane's settings.local.json differs from the main checkout's only by create's excludes."""
    try:
        data = read_json(mine, mine.name)
        before = read_json(original, original.name)
    except SettingsError:
        return False
    ours = set(main_instruction_excludes(main))
    excludes = [entry for entry in data.get("claudeMdExcludes", []) if entry not in ours]
    data = {key: value for key, value in data.items() if key != "claudeMdExcludes"}
    if excludes:
        data["claudeMdExcludes"] = excludes
    return data == before


# ---- state of one folder ------------------------------------------------------------------------

def branch_of(folder: Path) -> str | None:
    name = git(folder, "rev-parse", "--abbrev-ref", "HEAD").strip()
    return None if name == "HEAD" else name


def ahead_behind(folder: Path, tip: str) -> tuple[int, int]:
    out = git(folder, "rev-list", "--left-right", "--count", f"HEAD...{tip}").split()
    return int(out[0]), int(out[1])


def dirty_count(folder: Path) -> int:
    return len(git(folder, "status", "--porcelain").splitlines())


def unpushed_count(folder: Path) -> int | None:
    if not git(folder, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False).strip():
        return None
    return int(git(folder, "rev-list", "--count", "@{u}..HEAD").strip())
