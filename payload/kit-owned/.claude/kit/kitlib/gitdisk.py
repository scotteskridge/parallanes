"""Where a folder's git working tree and git dirs are, read from disk (plan 15, decision 120).

Each git call costs ~70 ms on Windows, and the hooks run on every tool call, so the normal layouts
are read from the files git documents (gitrepository-layout): a `.git` folder, or a `.git` file whose
`gitdir:` line names the git dir, and that dir's `commondir`. Only a `.git` that is plainly what
`git init` or `git worktree add` writes is answered here; anything else is UNKNOWN, and the caller
asks git as before: an unusual layout is slower, never answered differently. When in doubt,
UNKNOWN: the protected guard trusts the root found here (review rounds 1 and 2). `config.find_root`
also asks git when the answer here holds no kit.toml.
"""

import os
import stat
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
_HEX = frozenset("0123456789abcdef")
_LIMIT = 65536  # bytes: more than any `.git` file, HEAD or config git writes; bigger asks git
# Extensions this module understands: worktreeConfig (read below) and relativeWorktrees (relative
# `gitdir:` and `commondir` paths, which git_dirs already resolves).
_EXTENSIONS = ("worktreeconfig", "relativeworktrees")


def _device(folder: Path) -> int:
    return os.stat(folder).st_dev


def toplevel(start: Path):
    """The working tree holding start, None when no folder above it holds a `.git`, or UNKNOWN."""
    if any(os.environ.get(name) for name in _GIT_ENV):
        return UNKNOWN
    start = Path(start).resolve()
    device = _device(start) if _CHECK_DEVICE else None
    for folder in (start, *start.parents):
        if folder.name == ".git" or (folder / "HEAD").exists():
            return UNKNOWN  # inside a git dir, or maybe a bare repository: git knows
        if device is not None and _device(folder) != device:
            return UNKNOWN
        dot = folder / ".git"
        if not dot.exists():
            continue
        dirs = git_dirs(folder)
        if dirs is None or _moves_worktree(*dirs):
            return UNKNOWN
        return folder
    return None


def git_dirs(top: Path) -> tuple[Path, Path] | None:
    """(git dir, common git dir) of the working tree top; None unless its `.git` is a plain one."""
    dot = top / ".git"
    if dot.is_dir():
        if (dot / "commondir").exists():
            return None
        return (dot, dot) if _is_repository(dot) else None
    text = _read(dot)
    if not text:
        return None
    text = text.rstrip("\r\n")
    # git takes the whole file but its line ending, and the path exactly as written after "gitdir: ".
    path = text.removeprefix("gitdir: ")
    if path == text or not path or path != path.strip() or "\n" in path or "\r" in path:
        return None
    git_dir = Path(os.path.normpath(top / path))
    if not _valid_head(git_dir):
        return None
    common = _read(git_dir / "commondir", missing="")
    if common is None:
        return None
    if not common:
        common_dir = git_dir  # no commondir: a separate git dir, or a submodule's own checkout
    else:
        common = common.rstrip("\r\n")
        if not common or common != common.strip():
            return None
        common_dir = Path(os.path.normpath(git_dir / common))
    return (git_dir, common_dir) if _is_repository(common_dir) else None


def _read(path: Path, missing=None) -> str | None:
    """The text of a small regular file; `missing` when there is none; None for anything else.

    Never follows a symlink and never reads a FIFO or a device: a FIFO `.git` hung every hook until
    its timeout let the call through (review round 3), and git itself skips a symlinked HEAD.
    """
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return missing
    except OSError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_size > _LIMIT:
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read(_LIMIT)
    except (OSError, UnicodeDecodeError):
        return None


def _is_repository(folder: Path) -> bool:
    """objects/ and refs/ git can search, a config and a HEAD as `git init` writes them."""
    return (
        all(os.access(folder / name, os.X_OK) and (folder / name).is_dir() for name in ("objects", "refs"))
        and (folder / "config").is_file()
        and _valid_head(folder)
    )


def _valid_head(git_dir: Path) -> bool:
    """A HEAD exactly as git writes it: `ref: refs/...`, or a lowercase object id."""
    head = _read(git_dir / "HEAD")
    if head is None:
        return False
    head = head.rstrip("\n")
    if head.startswith("ref: refs/"):
        return head == head.strip()
    return len(head) in (40, 64) and _HEX.issuperset(head)


def _moves_worktree(git_dir: Path, common: Path) -> bool:
    """Anything in the config that git reads differently, or that may put the working tree away from
    its `.git`: `core.worktree`, a `bare` that isn't false, `[include]`, a repository format or
    extension the kit doesn't know. With `extensions.worktreeConfig` (Claude Code's worktrees turn it
    on), the worktree's own `config.worktree` is read the same way. Loose by design: a false alarm
    only means asking git.
    """
    text = _read(common / "config")
    if text is None:
        return True
    unclear, per_worktree = _read_config(text, extensions_allowed=True)
    if unclear:
        return True
    if not per_worktree:
        return False
    text = _read(git_dir / "config.worktree", missing="")
    return text is None or _read_config(text, extensions_allowed=False)[0]


def _read_config(text: str, extensions_allowed: bool) -> tuple[bool, bool]:
    """(unclear, worktreeConfig on) for one config file's text."""
    section, per_worktree = "", False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("["):
            inner = line[1:-1] if line.endswith("]") and line.count("]") == 1 else None
            if inner is None or not inner or inner != inner.strip():
                return True, per_worktree  # a header git may reject, or a key on its line
            section = inner.split('"')[0].strip().lower()
            if section.startswith("include"):
                return True, per_worktree  # [include] / [includeIf]: another file could set anything
            continue
        key, equals, value = line.partition("=")
        key = key.strip().lower()
        value = value.split(";")[0].split("#")[0].strip().strip('"').lower()
        false = equals and value in ("false", "no", "off", "0")
        if key == "worktree" or (key == "bare" and not false):
            return True, per_worktree
        if section == "core" and key == "repositoryformatversion" and value not in ("0", "1"):
            return True, per_worktree
        if section == "extensions":
            if not extensions_allowed or key not in _EXTENSIONS:
                return True, per_worktree  # objectformat, refstorage, ...: git's to read
            if key == "worktreeconfig":
                per_worktree = not false
    return False, per_worktree
