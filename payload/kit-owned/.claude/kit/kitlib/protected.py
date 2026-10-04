"""Protected paths, secrets and commands from `[protected]` in kit.toml (plan 03).

Deny rules in `settings.json` are the primary protection (decision 15). This module is the backstop
behind them, used by the PreToolUse hook (`check_tool_call`), and the check that pre-commit and CI
run on changed files (`check`).
"""
import os
import re
from pathlib import Path

from . import commands
from .findings import Finding
from .globs import matches, normalize

CHECK = "protected"
ALLOW_VARIABLE = "KIT_ALLOW_PROTECTED"

# The kit's own configuration: whoever can edit these can switch the protection off (decision 30).
KIT_GUARD = [".claude/settings.json", ".claude/kit.toml", ".claude/kit/**", ".githooks/**"]

FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash": "bash", "PowerShell": "powershell"}


def _matching(path: str, patterns, removes: bool = False) -> str | None:
    """The first pattern path falls under, also when path is a folder holding matching files:
    `Remove-Item vendor` deletes everything `vendor/**` protects, `rm -rf src` deletes `src/vendor/`."""
    path = normalize(path).rstrip("/")
    path = "" if path == "." else path
    for pattern in patterns:
        if path and (matches(path, pattern) or matches(path + "/__kit_probe__", pattern)):
            return pattern
        if removes and _inside(pattern, path):
            return pattern
    return None


def _inside(pattern: str, folder: str) -> bool:
    """Whether an anchored pattern's fixed folders lie inside folder ("" is the project root).
    A pattern without a slash can match at any depth, so it says nothing about a given folder."""
    pattern = normalize(pattern).lstrip("/")
    if "/" not in pattern.rstrip("/"):
        return False
    fixed = re.split(r"[*?\[]", pattern, maxsplit=1)[0]
    return fixed.startswith(folder + "/") if folder else bool(fixed)


def path_reason(protected, path: str, bypass: bool, removes: bool = False) -> str | None:
    """Why changing path is blocked, or None.

    bypass: the session runs in bypassPermissions mode. removes: path is being deleted or moved
    away, so a protected path anywhere inside it counts too.
    """
    pattern = _matching(path, protected.paths, removes)
    if pattern:
        return f"{normalize(path)} is protected (matches {pattern!r} in [protected].paths, .claude/kit.toml)"
    pattern = _matching(path, protected.secrets, removes)
    if pattern:
        return f"{normalize(path)} holds secrets (matches {pattern!r} in [protected].secrets, .claude/kit.toml)"
    if bypass and protected.guard_kit:
        pattern = _matching(path, KIT_GUARD, removes)
        if pattern:
            return (
                f"{normalize(path)} is the kit's own configuration, and edits to it need the owner's "
                "approval, which bypassPermissions mode can't ask for"
            )
    return None


def check(config, paths) -> list[Finding]:
    """Findings for changed paths that are protected or secret. Kit config changes are normal commits."""
    findings = []
    for path in paths:
        reason = path_reason(config.protected, path, bypass=False)
        if reason:
            message = f"{reason}. If this change is intended, commit it with {ALLOW_VARIABLE}=1."
            findings.append(Finding(path=normalize(path), line=0, check=CHECK, message=message))
    return sorted(findings)


def allowed_by_human() -> bool:
    return os.environ.get(ALLOW_VARIABLE) == "1"


def check_tool_call(payload: dict, root: Path, config) -> str | None:
    """Why Claude Code should block this tool call, or None to let the normal permission flow decide."""
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    cwd = Path(payload.get("cwd") or root)
    bypass = payload.get("permission_mode") == "bypassPermissions"
    protected = config.protected

    if tool in FILE_TOOLS:
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
        return _target_reason(protected, root, cwd, file_path, bypass) if file_path else None

    shell = SHELL_TOOLS.get(tool)
    if shell is None:
        return None
    text = tool_input.get("command")
    if not isinstance(text, str):
        raise ValueError(f"{tool} call without a command string")
    reason = commands.disables_checks(text, shell)
    if reason:
        return reason
    for offending, pattern in commands.find_protected(text, shell, protected.commands):
        return f"`{offending}` matches the protected command {pattern!r} ([protected].commands, .claude/kit.toml)"
    for target in commands.write_targets(text, shell):
        reason = _target_reason(protected, root, cwd, target, bypass)
        if reason:
            return reason
    for target in commands.removed_targets(text, shell):
        reason = _target_reason(protected, root, cwd, target, bypass, removes=True)
        if reason:
            return reason
    return None


def _target_reason(protected, root: Path, cwd: Path, target: str, bypass: bool, removes: bool = False) -> str | None:
    rel = relative(root, cwd, target)
    return None if rel is None else path_reason(protected, rel, bypass, removes)


def relative(root: Path, cwd: Path, target: str) -> str | None:
    """target as a project-relative POSIX path, or None if it lies outside the project."""
    path = Path(target.replace("\\", "/")) if os.sep == "/" else Path(target)
    absolute = Path(os.path.normpath(cwd / path))  # normpath, not resolve: the file may not exist yet
    try:
        rel = absolute.relative_to(Path(os.path.normpath(root)))
    except ValueError:
        try:  # a symlinked or differently-cased root (macOS /private, Windows short names)
            rel = absolute.resolve().relative_to(root.resolve())
        except (ValueError, OSError):
            return None
    return rel.as_posix()
