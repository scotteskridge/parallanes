"""The kit's hooks in `.claude/settings.json` (plan 08, decision 100).

Like the permission rules (decision 29), the hook groups the kit wrote are recorded, in the
manifest: a re-run adds what's missing and removes only groups it wrote that are no longer
expected. A group the owner wrote is never touched, even an identical one. `[hooks]` in kit.toml
switches rules-check or lane-router off; a kit hook the owner only deleted comes back, said aloud
(decision 102).

Commands go through `.claude/kit/hook`, which takes Python from the gitignored `python-path`, so the
committed settings never hold a machine's interpreter. The `command` form with `sh` is the one the
reviewer's guard already runs live; whether placeholders expand in the exec-form `args` isn't
documented, so it isn't used.
"""

TOOLS_THAT_EDIT = "Edit|Write|MultiEdit|NotebookEdit"
TIMEOUT = 30  # seconds; the default is 600, and a stuck hook shouldn't stall a session that long

# (event, matcher or None, hook name). Fail modes live in kitlib/hooks.py and the launcher.
WIRING = [
    ("PreToolUse", "Bash|PowerShell|" + TOOLS_THAT_EDIT, "protected"),
    ("PreToolUse", TOOLS_THAT_EDIT, "ownership"),
    ("PostToolUse", TOOLS_THAT_EDIT, "rules-check"),
    ("SessionStart", None, "lane-router"),
]


# The security backstop behind the deny rules: kit.toml can't switch it off (decision 102).
ALWAYS_ON = "protected"


def _command(name: str) -> str:
    return f'sh "$CLAUDE_PROJECT_DIR/.claude/kit/hook" {name}'


def _group(matcher, name: str) -> dict:
    hook = {"type": "command", "command": _command(name), "timeout": TIMEOUT}
    return {"matcher": matcher, "hooks": [hook]} if matcher else {"hooks": [hook]}


def expected(off=frozenset()) -> dict:
    """The kit's groups by event, without the hooks `[hooks]` in kit.toml switched off."""
    if ALWAYS_ON in off:
        raise ValueError(f"the {ALWAYS_ON} hook can't be switched off")
    groups = {}
    for event, matcher, name in WIRING:
        if name not in off:
            groups.setdefault(event, []).append(_group(matcher, name))
    return groups


class HooksError(ValueError):
    """settings.json's hooks, or the manifest's record of them, aren't in the expected shape."""


def _commands(group: dict) -> set:
    return {hook.get("command") for hook in group.get("hooks", []) if isinstance(hook, dict)}


def check(hooks, recorded) -> None:
    if not isinstance(hooks, dict) or not all(
        isinstance(groups, list) and all(isinstance(group, dict) for group in groups) for groups in hooks.values()
    ):
        raise HooksError('.claude/settings.json: "hooks" must map event names to lists of hook groups')
    if not isinstance(recorded, list) or not all(
        isinstance(entry, dict) and isinstance(entry.get("event"), str) and isinstance(entry.get("group"), dict)
        for entry in recorded
    ):
        raise HooksError('.claude/kit/manifest.json: "hooks" must be a list of {"event", "group"} entries')


def merge(settings: dict, recorded: list, off=frozenset()) -> list:
    """Update settings in place; return the new record of groups the kit wrote.

    A kit group is found by its command, so one the owner edited (a longer timeout) still counts as
    present and isn't added again. Only an unedited copy of a group the kit no longer wants (or that
    `off` switches off) is removed.
    """
    hooks = settings.get("hooks", {})
    check(hooks, recorded)
    wanted = expected(off)
    wanted_keys = {(event, command) for event, groups in wanted.items() for g in groups for command in _commands(g)}
    for entry in recorded:
        event, group = entry["event"], entry["group"]
        stale = not any((event, command) in wanted_keys for command in _commands(group))
        groups = hooks.get(event, [])
        if stale and group in groups:
            groups.remove(group)
            if not groups:
                del hooks[event]
    recorded_keys = {(entry["event"], command) for entry in recorded for command in _commands(entry["group"])}
    record = []
    for event, groups in wanted.items():
        present = hooks.setdefault(event, [])
        for group in groups:
            (command,) = _commands(group)
            if not any(command in _commands(other) for other in present):
                present.append(group)
                record.append({"event": event, "group": group})
            elif (event, command) in recorded_keys:
                record.append({"event": event, "group": group})
            # else: the owner wrote a group running the same command; it stays theirs and unrecorded
    if hooks:
        settings["hooks"] = hooks
    return record


def recorded_names(recorded: list) -> set:
    """The kit hooks the record holds. merge drops a switched-off hook from it but keeps one the
    owner only deleted, so a missing hook that isn't recorded was switched back on (or is new)."""
    commands = {command for entry in recorded for command in _commands(entry["group"])}
    return {name for _, _, name in WIRING if _command(name) in commands}


def _running(settings: dict) -> set:
    return {
        command for groups in settings.get("hooks", {}).values() for group in groups for command in _commands(group)
    }


def missing(settings: dict, off=frozenset()) -> list:
    """The kit hooks merge will add: none of the groups under their event runs their command.

    Checked per event, as merge does. On a re-run each one is said aloud, recorded or not, so a
    deleted hook coming back isn't a surprise; the way out is `[hooks]` in kit.toml.
    """
    hooks = settings.get("hooks", {})
    return [
        name
        for event, _, name in WIRING
        if name not in off and not any(_command(name) in _commands(group) for group in hooks.get(event, []))
    ]


def still_running(settings: dict, off) -> list:
    """Switched-off hooks settings.json still runs: a copy the owner edited or wrote stays theirs."""
    running = _running(settings)
    return [name for _, _, name in WIRING if name in off and _command(name) in running]
