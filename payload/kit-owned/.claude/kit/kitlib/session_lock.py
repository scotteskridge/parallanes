"""Claude Code's session lock on a lane worktree (decision 119, plan 14).

`claude --worktree <lane>` locks the lane with the reason `claude session <name> (pid N)` before
SessionStart hooks run, `N` being Claude Code's own process (checked live). Interactive, it deletes
a lane's folder on exit when the session changed nothing; a `-p` run leaves the lock behind, and git
then refuses `worktree remove` (decision 107). Only that reason counts: an owner's own
`git worktree lock` is theirs.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import lanes

_REASON = re.compile(r"claude session .+ \(pid ([0-9]+)\)\Z")  # ASCII only: \d takes other scripts' digits
_MAX_PID = 2**31 - 1  # past this os.kill overflows a C int, and Windows' DWORD cuts it to another pid


@dataclass(frozen=True)
class SessionLock:
    pid: int
    running: bool  # also True when liveness can't be checked: never clear a lock on a guess


def pid_of(reason: str | None) -> int | None:
    """The pid in a Claude Code session lock's reason; None for any other lock or none."""
    found = _REASON.fullmatch(reason or "")
    return int(found.group(1)) if found else None


def find(main: Path, folder: Path) -> SessionLock | None:
    """Claude Code's lock on the worktree at folder, from one `git worktree list` in main."""
    pid = pid_of(lanes.lock_reason(main, folder))
    return SessionLock(pid, is_running(pid)) if pid is not None else None


def is_running(pid: int) -> bool:
    if not 0 < pid <= _MAX_PID:
        return True  # 0 and below mean process groups to os.kill; too big can't be checked (review round 1)
    if os.name == "nt":
        return _windows_running(pid)
    try:
        os.kill(pid, 0)  # signal 0 only checks; on Windows os.kill would end the process
    except ProcessLookupError:
        return False
    except (OSError, OverflowError):
        return True  # it exists but isn't ours (PermissionError), or the check failed
    return True


def _windows_running(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except OSError:
        return True
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER: no process has this pid
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)
