"""Find the project root and load `.claude/kit.toml`.

Validation is strict (decision 24): an unknown key or a wrong type is an error naming the key, so a
typo can't silently switch a rule off. Tables that later parts of the kit own (`lanes`) are accepted
here and validated by the code that reads them.
"""
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import commands, globs

CONFIG_REL = Path(".claude") / "kit.toml"

_TOP_LEVEL = {"project", "checks", "lanes", "protected"}
_PROJECT_KEYS = {
    "name": str,
    "description": str,
    "test_command": str,
    "integration_branch": str,
    "merge_mode": str,
    "worktree_root": str,
    "ownership": str,
    "shared_paths": list,
}
_CHECKS_KEYS = {"rules": list}
_PROTECTED_KEYS = {"paths": list, "commands": list, "secrets": list, "guard_kit": bool}

# Used when [protected] leaves a key out, so a project that never wrote the table is still guarded.
# `git clean -f` rather than `-fdx`: every flag in a pattern must be present, and `-fd` destroys too.
DEFAULT_COMMANDS = [
    "git push --force",
    "git push -f",
    "git reset --hard",
    "git clean -f",
    "git commit --no-verify",
    "git commit -n",
]
# File names, not `.env.*`: an allow rule can't carve `.env.example` out of a deny (decision 31).
DEFAULT_SECRETS = [".env", ".env.local", ".env.*.local"]
_RULE_KEYS = {
    "id": (str, True),
    "pattern": (str, True),
    "paths": (list, True),
    "message": (str, True),
    "exclude": (list, False),
    "ignore_comments": (bool, False),
}


class ConfigError(Exception):
    """kit.toml exists but can't be used. The message names the file, key and problem."""


class ConfigMissing(ConfigError):
    """No kit.toml: the kit isn't set up in this project."""


@dataclass(frozen=True)
class Rule:
    id: str
    regex: re.Pattern
    paths: list
    message: str
    exclude: list = field(default_factory=list)
    ignore_comments: bool = True


@dataclass(frozen=True)
class Protected:
    paths: list = field(default_factory=list)
    commands: list = field(default_factory=lambda: list(DEFAULT_COMMANDS))
    secrets: list = field(default_factory=lambda: list(DEFAULT_SECRETS))
    guard_kit: bool = True


@dataclass(frozen=True)
class Config:
    project: dict
    rules: list
    raw: dict
    protected: Protected = field(default_factory=Protected)


def find_root(start: Path) -> Path:
    """The git top level containing start (a lane worktree is its own top level).

    Outside git, the nearest folder above start that has .claude/kit.toml; failing that, start.
    """
    start = Path(start).resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    for folder in (start, *start.parents):
        if (folder / CONFIG_REL).is_file():
            return folder
    return start


def load(root: Path) -> Config:
    path = Path(root) / CONFIG_REL
    if not path.is_file():
        raise ConfigMissing(f"{CONFIG_REL.as_posix()} not found in {root}")
    try:
        # utf-8-sig: Windows PowerShell 5.1 writes a byte-order mark that TOML rejects.
        raw = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{CONFIG_REL.as_posix()}: not valid TOML: {error}") from None

    _check_keys(raw, dict.fromkeys(_TOP_LEVEL, object), "top level")
    project = raw.get("project", {})
    _check_table(project, "[project]")
    _check_keys(project, _PROJECT_KEYS, "[project]")
    checks = raw.get("checks", {})
    _check_table(checks, "[checks]")
    _check_keys(checks, _CHECKS_KEYS, "[checks]")
    rules = [_rule(entry, number) for number, entry in enumerate(checks.get("rules", []), start=1)]

    seen = set()
    for rule in rules:
        if rule.id in seen:
            raise ConfigError(f"{CONFIG_REL.as_posix()}: duplicate rule id {rule.id!r}")
        seen.add(rule.id)
    return Config(project=project, rules=rules, raw=raw, protected=_protected(raw.get("protected", {})))


def _protected(table) -> Protected:
    where = "[protected]"
    _check_table(table, where)
    _check_keys(table, _PROTECTED_KEYS, where)
    for key in ("paths", "secrets"):
        for value in _strings(table, key, where):
            # Patterns are project-relative: the same text becomes a root-anchored deny rule.
            if value.startswith(("//", "~")) or ".." in value.replace("\\", "/").split("/"):
                _fail(f"{where}: {key!r}: {value!r} must be a path inside the project")
            try:
                globs.validate(value)
            except ValueError as error:
                _fail(f"{where}: {key!r}: {error}")
    for value in _strings(table, "commands", where):
        try:
            commands.parse_pattern(value)
        except ValueError as error:
            _fail(f"{where}: 'commands': {value!r}: {error}")
    defaults = Protected()
    return Protected(
        paths=list(table.get("paths", defaults.paths)),
        commands=list(table.get("commands", defaults.commands)),
        secrets=list(table.get("secrets", defaults.secrets)),
        guard_kit=table.get("guard_kit", defaults.guard_kit),
    )


def _strings(table: dict, key: str, where: str) -> list:
    values = table.get(key, [])
    if not all(isinstance(value, str) for value in values):
        _fail(f"{where}: {key!r} must be a list of strings")
    return values


def _rule(entry, number: int) -> Rule:
    where = f"[[checks.rules]] #{number}"
    _check_table(entry, where)
    if isinstance(entry.get("id"), str):
        where = f"[[checks.rules]] {entry['id']!r}"
    _check_keys(entry, {key: kind for key, (kind, _) in _RULE_KEYS.items()}, where)
    for key, (_, required) in _RULE_KEYS.items():
        if required and key not in entry:
            _fail(f"{where}: missing required key {key!r}")
    for key in ("id", "pattern", "message"):
        if not entry[key].strip():
            _fail(f"{where}: {key!r} must not be empty")
    for key in ("paths", "exclude"):
        values = entry.get(key, [])
        if not all(isinstance(value, str) for value in values):
            _fail(f"{where}: {key!r} must be a list of strings")
        for value in values:
            try:
                globs.validate(value)
            except ValueError as error:
                _fail(f"{where}: {key!r}: {error}")
    if not entry["paths"]:
        _fail(f"{where}: 'paths' must list at least one glob")
    try:
        regex = re.compile(entry["pattern"])
    except re.error as error:
        _fail(f"{where}: 'pattern' is not a valid regular expression: {error}")
    return Rule(
        id=entry["id"],
        regex=regex,
        paths=list(entry["paths"]),
        message=entry["message"],
        exclude=list(entry.get("exclude", [])),
        ignore_comments=entry.get("ignore_comments", True),
    )


def _check_table(value, where: str) -> None:
    if not isinstance(value, dict):
        _fail(f"{where} must be a table")


def _check_keys(table: dict, allowed: dict, where: str) -> None:
    for key, value in table.items():
        if key not in allowed:
            _fail(f"{where}: unknown key {key!r} (allowed: {', '.join(sorted(allowed))})")
        kind = allowed[key]
        if kind is not object and not isinstance(value, kind):
            _fail(f"{where}: {key!r} must be a {kind.__name__}, not {type(value).__name__}")


def _fail(message: str):
    raise ConfigError(f"{CONFIG_REL.as_posix()}: {message}")
