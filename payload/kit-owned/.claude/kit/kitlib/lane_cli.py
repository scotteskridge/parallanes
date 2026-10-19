"""`parallanes lanes ...`: runs one lanes command and turns its result into output and an exit code.

Imported lazily by cli.py, so a fault in the lane code can't take the protected guard down.
"""

import sys
from pathlib import Path

from kitlib import lane_cycle, lane_owners, lane_setup, lane_status, lanes
from kitlib.config import ConfigError, find_root, load

OK, UNFINISHED, USAGE = 0, 1, 2


def run(args) -> int:
    try:
        here = Path.cwd()
        config = load(find_root(here))
        command = args.lanes_command
        if command == "create":
            lines = lane_setup.create(here, config, args.names, args.dry_run)
            # Said where lanes are set up too, so a split's overlaps are seen before work starts.
            notes, problems = lane_owners.tracked_overlaps(lanes.main_checkout(here), config)
            lines += [f"Note: {note}" for note in notes] + [f"! {problem}" for problem in problems]
            lines += _lane_hooks_note(lanes.main_checkout(here), config)
        elif command == "remove":
            lines = [lane_setup.remove(here, config, args.name, args.force)]
        elif command == "start":
            lines = lane_cycle.start(here, config, args.task, args.abandon)
        elif command == "sync":
            lines = lane_cycle.sync(here, config)
        elif command == "finish":
            lines = lane_cycle.finish(here, config, args.title, args.body_file)
        elif command == "suggest":
            lines = _suggest(lanes.main_checkout(here), config)
        else:
            lines = [lane_status.format_status(lane_status.status(here, config, args.offline))]
    except lane_setup.PartialCreate as error:
        print("\n".join(error.lines))
        print(f"parallanes: {error}", file=sys.stderr)
        return USAGE
    except lanes.Unfinished as error:  # before LaneError, its base class
        print(f"parallanes: {error}", file=sys.stderr)
        return UNFINISHED
    except (ConfigError, lanes.LaneError) as error:
        print(f"parallanes: {error}", file=sys.stderr)
        return USAGE
    print("\n".join(lines))
    return OK


def _lane_hooks_note(main: Path, config) -> list[str]:
    """A solo install has the kit's hooks but not the two lane hooks (decision 121); lanes added by
    hand afterwards would run without them, so say how to add them. A hook kit.toml switches off
    isn't missing (review round 1)."""
    import json

    try:
        settings = json.loads((main / ".claude" / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []  # no settings, or ones the kit's own checks report on
    # Read loosely: a malformed entry is `check settings`' business, not a reason to fail here.
    kit = []
    events = settings.get("hooks") if isinstance(settings, dict) else None
    for groups in events.values() if isinstance(events, dict) else ():
        for group in groups if isinstance(groups, list) else ():
            for hook in group.get("hooks", []) if isinstance(group, dict) else ():
                command = hook.get("command") if isinstance(hook, dict) else None
                if isinstance(command, str) and ".claude/kit/hook" in command:
                    kit.append(command)
    wanted = {"ownership", "lane-router"} - set(config.hooks.switched_off)
    if config.lane_settings.ownership == "off":
        wanted.discard("ownership")
    missing = sorted(name for name in wanted if not any(command.endswith(f" {name}") for command in kit))
    if not kit or not missing:
        return []  # not the kit's hooks at all, or the lane hooks are there
    return [
        f"Note: .claude/settings.json has the kit's hooks but not {' or '.join(missing)}: "
        "re-run the kit's installer with --profile lanes to add them."
    ]


def _suggest(main: Path, config) -> list[str]:
    """The guess from the main checkout's tracked files, ready to paste into kit.toml (decision 122)."""
    from kitlib import gitfiles, lane_suggest

    found, why = lane_suggest.suggest(gitfiles.tracked(main), config.project.get("integration_branch", "main"))
    if not found:
        return [f"No lanes to suggest: {why}."]
    note = " .claude/kit.toml already has lanes: compare before changing them." if config.lanes else ""
    return [
        "# A guess from the project's folders: check each lane's paths, then add the tables to .claude/kit.toml."
        + note,
        lane_suggest.to_toml(found),
    ]
