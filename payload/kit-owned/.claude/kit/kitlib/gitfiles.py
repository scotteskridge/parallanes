"""Which files to check, and their text: from disk, from the git index, or changed since a base."""
import subprocess
from pathlib import Path

_SNIFF = 8192  # bytes looked at to decide whether a file is binary


class GitError(Exception):
    """A git command failed; the message includes git's own error."""


def _git(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise GitError(f"git {' '.join(args)}: {error}") from None
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise GitError(f"git {' '.join(args)} failed: {message}")
    return result.stdout


def _names(output: bytes) -> list[str]:
    return [name for name in output.decode("utf-8", "replace").split("\0") if name]


def decode(data: bytes) -> str | None:
    """Text of a file, or None for a binary file (a NUL byte near the start)."""
    if b"\0" in data[:_SNIFF]:
        return None
    return data.decode("utf-8", "replace")


def tracked(root: Path) -> list[str]:
    return _names(_git(root, "ls-files", "-z"))


def staged(root: Path) -> list[str]:
    """Files added, copied, modified or renamed in the index (deleted files have nothing to check)."""
    return _names(_git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"))


def changed_since(root: Path, base: str) -> list[str]:
    """Files changed on this branch since it left base (merge-base diff, as a pull request sees it)."""
    return _names(_git(root, "diff", "--name-only", "--diff-filter=ACMR", "-z", f"{base}...HEAD"))


def read_staged(root: Path, path: str) -> str | None:
    """The staged version of a file: what the commit will contain, not the working tree."""
    return decode(_git(root, "show", f":{path}"))


def read_worktree(root: Path, path: str) -> str | None:
    """The file on disk, or None if it is missing or binary."""
    try:
        return decode((root / path).read_bytes())
    except OSError:
        return None
