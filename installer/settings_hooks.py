"""The kit's hooks in `.claude/settings.json` (plan 08, decision 100).

Like the permission rules (decision 29), the hook groups the kit wrote are recorded, in the
manifest: a re-run adds what's missing and removes only groups it wrote that are no longer
expected. A group the owner wrote is never touched, even an identical one.

Commands go through `.claude/kit/hook`, which takes Python from the gitignored `python-path`, so the
committed settings never hold a machine's interpreter. The `command` form with `sh` is the one the
reviewer's guard already runs live; whether placeholders expand in the exec-form `args` isn't
documented, so it isn't used.
"""

import json

TOOLS_THAT_EDIT = "Edit|Write|MultiEdit|NotebookEdit"
TIMEOUT = 30  # seconds; the default is 600, and a stuck hook shouldn't stall a session that long

# (event, matcher or None, hook name). Fail modes live in kitlib/hooks.py and the launcher.
WIRING = [
    ("PreToolUse", "Bash|PowerShell|" + TOOLS_THAT_EDIT, "protected"),
    ("PreToolUse", TOOLS_THAT_EDIT, "ownership"),
    ("PostToolUse", TOOLS_THAT_EDIT, "rules-check"),
    ("SessionStart", None, "lane-router"),
]


def _group(matcher, name: str) -> dict:
    hook = {"type": "command", "command": f'sh "$CLAUDE_PROJECT_DIR/.claude/kit/hook" {name}', "timeout": TIMEOUT}
    return {"matcher": matcher, "hooks": [hook]} if matcher else {"hooks": [hook]}


def expected() -> dict:
    groups = {}
    for event, matcher, name in WIRING:
        groups.setdefault(event, []).append(_group(matcher, name))
    return groups


class HooksError(ValueError):
    """settings.json's hooks aren't in the shape Claude Code reads; left untouched."""


def merge(settings: dict, recorded: list) -> list:
    """Update settings in place; return the new record of groups the kit wrote."""
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict) or not all(isinstance(groups, list) for groups in hooks.values()):
        raise HooksError('.claude/settings.json: "hooks" must map event names to lists')
    wanted = expected()
    record = []
    for entry in recorded:
        event, group = entry["event"], entry["group"]
        groups = hooks.get(event, [])
        if group not in wanted.get(event, []) and group in groups:
            groups.remove(group)  # the first copy: the one the kit added
            if not groups:
                del hooks[event]
    recorded_now = {(entry["event"], _key(entry["group"])) for entry in recorded}
    for event, groups in wanted.items():
        present = hooks.setdefault(event, [])
        for group in groups:
            if group not in present:
                present.append(group)
                record.append({"event": event, "group": group})
            elif (event, _key(group)) in recorded_now:
                record.append({"event": event, "group": group})
            # else: the owner wrote the same group; it stays theirs and unrecorded
    if hooks:
        settings["hooks"] = hooks
    return record


def _key(group: dict) -> str:
    return json.dumps(group, sort_keys=True)
