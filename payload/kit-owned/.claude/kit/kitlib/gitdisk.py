"""Where a folder's git working tree and git dirs are, read from disk (plan 15, decision 120).

Each git call costs ~70 ms on Windows, and the hooks run on every tool call, so the normal layouts
are read from the files git documents (gitrepository-layout): a `.git` folder, or a `.git` file whose
`gitdir:` line names the git dir, and that dir's `commondir`. Anything else is UNKNOWN, and the
caller asks git as before: an unusual layout is slower, never answered differently. When in doubt,
UNKNOWN: the protected guard trusts the root found here (review round 1).
"""

import os
from pathlib import Path

UNKNOWN = object()  # this layout is git's to answer

# Each changes where git looks for the repository, where it stops looking, or which dirs it uses.
_GIT_ENV = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
)
# git stops at a mount point (unless told otherwise); the walk can't know what it would answer
# there. Not on Windows, where a walk can't leave its drive.
_CHECK_DEVICE = os.name != "nt"


def _device(folder: Path) -> int:
    return os.stat(folder).st_dev


def toplevel(start: Path):
    """The working tree holding start, None when no folder above it holds a `.git`, or UNKNOWN."""
    if any(os.environ.get(name) for name in _GIT_ENV):
        return UNKNOWN
    start = Path(start).resolve()
    device = _device(start) if _CHECK_DEVICE else None
    for folder in (start, *start.parents):
        if folder.name == ".git" or _is_repository(folder):
            return UNKNOWN  # inside a git dir, or a bare repository: no working tree, as git says
        if device is not None and _device(folder) != device:
            return UNKNOWN
        dot = folder / ".git"
        if dot.is_dir():
            if not _is_repository(dot):
                continue  # not a repository: git skips it and keeps looking up
            return UNKNOWN if not (dot / "config").is_file() or _moves_worktree(dot) else folder
        if dot.exists():
            dirs = git_dirs(folder)
            if dirs is None or any(_moves_worktree(found) for found in dirs):
                return UNKNOWN
            return folder
    return None


def git_dirs(top: Path) -> tuple[Path, Path] | None:
    """(git dir, common git dir) of the working tree top; None when its `.git` can't be read."""
    dot = top / ".git"
    if dot.is_dir():
        return dot, dot
    try:
        line = dot.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, UnicodeDecodeError, IndexError):
        return None
    if not line.startswith("gitdir: "):
        return None
    git_dir = Path(os.path.normpath(top / line[len("gitdir: ") :].strip()))
    if not _valid_head(git_dir):
        return None
    try:
        common = (git_dir / "commondir").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        common_dir = git_dir  # a separate git dir, or a submodule's own checkout
    except (OSError, UnicodeDecodeError):
        return None
    else:
        common_dir = Path(os.path.normpath(git_dir / common))
    return (git_dir, common_dir) if _is_repository(common_dir) else None


def _is_repository(folder: Path) -> bool:
    """What git checks before it takes a folder as a git dir: objects/, refs/ and a HEAD that names a
    ref or a commit. A folder that fails is skipped by git, so it must not end the walk here."""
    if not ((folder / "objects").is_dir() and (folder / "refs").is_dir()):
        return False
    return _valid_head(folder)


def _valid_head(git_dir: Path) -> bool:
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return False
    if head.startswith("ref: refs/"):
        return True
    return len(head) in (40, 64) and all(char in "0123456789abcdef" for char in head)


def _moves_worktree(git_dir: Path) -> bool:
    """The working tree may not be where the `.git` is: `core.worktree` set, `core.bare` true, or a
    per-worktree config (`extensions.worktreeConfig`), which can set either. Read loosely, in any
    section: a false alarm only means asking git, so anything unclear counts.
    """
    try:
        text = (git_dir / "config").read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return False  # a linked worktree's own git dir has none
    except OSError:
        return True
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            if "=" in line or line.count("]") != 1 or not line.endswith("]"):
                return True  # a key on the section's own line: not worth parsing here
            if line.lower().startswith("[include"):
                return True  # [include] / [includeIf]: another file could set either key
            continue
        key, equals, value = line.partition("=")
        key = key.strip().lower()
        value = value.split(";")[0].split("#")[0].strip().lower()
        if key in ("worktree", "worktreeconfig"):
            return True
        if key == "bare" and (not equals or value not in ("false", "no", "off", "0")):
            return True
    return False
