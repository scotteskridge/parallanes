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
        elif command == "remove":
            lines = [lane_setup.remove(here, config, args.name, args.force)]
        elif command == "start":
            lines = lane_cycle.start(here, config, args.task, args.abandon)
        elif command == "sync":
            lines = lane_cycle.sync(here, config)
        elif command == "finish":
            lines = lane_cycle.finish(here, config, args.title, args.body_file)
        elif command == "suggest":
            lines = _suggest(lanes.main_checkout(here))
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


def _suggest(main: Path) -> list[str]:
    """The guess from the main checkout's tracked files, ready to paste into kit.toml (decision 122)."""
    from kitlib import gitfiles, lane_suggest

    found, why = lane_suggest.suggest(gitfiles.tracked(main))
    if not found:
        return [f"No lanes to suggest: {why}."]
    return [
        "# A guess from the project's folders: check each lane's paths, then add the tables to .claude/kit.toml.",
        lane_suggest.to_toml(found),
    ]
