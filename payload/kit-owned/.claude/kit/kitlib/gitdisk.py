"""Where a folder's git working tree and git dirs are, read from disk (plan 15, decision 120).

Each git call costs ~70 ms on Windows, and the hooks run on every tool call, so the normal layouts
are read from the files git documents (gitrepository-layout): a `.git` folder, or a `.git` file whose
`gitdir:` line names the git dir, and that dir's `commondir`. Anything else is UNKNOWN, and the
caller asks git as before: an unusual layout is slower, never answered differently.
"""

import os
from pathlib import Path

UNKNOWN = object()  # this layout is git's to answer

# Each changes where git looks for the repository or where it stops looking.
_GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_CEILING_DIRECTORIES", "GIT_DISCOVERY_ACROSS_FILESYSTEM")


def toplevel(start: Path):
    """The working tree holding start, None when no folder above it holds a `.git`, or UNKNOWN."""
    if any(os.environ.get(name) for name in _GIT_ENV):
        return UNKNOWN
    start = Path(start).resolve()
    for folder in (start, *start.parents):
        dot = folder / ".git"
        if dot.is_dir():
            if not (dot / "HEAD").is_file():
                continue  # not a repository: git skips it and keeps looking up
            return UNKNOWN if _moves_worktree(dot) else folder
        if dot.exists():
            return folder if git_dirs(folder) is not None else UNKNOWN
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
    if not (git_dir / "HEAD").is_file():
        return None
    try:
        common = (git_dir / "commondir").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return git_dir, git_dir  # a submodule's own checkout: its git dir is the common one
    except (OSError, UnicodeDecodeError):
        return None
    return git_dir, Path(os.path.normpath(git_dir / common))


def _moves_worktree(dot: Path) -> bool:
    """`core.worktree` set, or `core.bare` true, in the repository's config: the working tree isn't
    dot's parent. Read loosely (such a key in any section): a false alarm only means asking git.
    """
    try:
        text = (dot / "config").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True
    for line in text.splitlines():
        key, equals, value = line.partition("=")
        key = key.strip().lower()
        if equals and (key == "worktree" or (key == "bare" and value.strip().lower() in _TRUE)):
            return True
    return False


_TRUE = ("true", "yes", "on", "1")
