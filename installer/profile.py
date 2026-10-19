"""Solo or lanes: which of the kit's hooks a project gets (plan 16, decision 121).

Solo is one agent at a time: the guardrails and the task loop, without the two hooks that only
matter with lanes (the session-start lane briefing and the ownership check on every edit). Lanes
gets every hook. The answer is saved with the others, so a re-run keeps it; `--profile` changes it.
"""

from .values import confirm

PROFILES = ("solo", "lanes")
LANE_HOOKS = frozenset({"lane-router", "ownership"})
QUESTION = "Run several agents at once, each in its own lane?"


class ProfileError(ValueError):
    """The profile asked for doesn't fit the project's kit.toml."""


def choose(flag: str | None, saved: dict, first_install: bool, interactive: bool, read=input) -> str:
    """The profile from --profile, else the saved answer, else the question (solo by default)."""
    if flag:
        return flag
    if saved.get("profile") in PROFILES:
        return saved["profile"]
    if not first_install:
        return "lanes"  # installed before profiles existed, with every hook: keep them
    if interactive:
        return "lanes" if confirm(QUESTION, False, read) else "solo"
    return "solo"


def effective(chosen: str, explicit: bool, has_lanes: bool) -> str:
    """Lanes already in kit.toml need the lane hooks, whatever was saved; asking for solo then is an error."""
    if not has_lanes:
        return chosen
    if explicit and chosen == "solo":
        raise ProfileError(
            ".claude/kit.toml has [[lanes]], which need the lane hooks: remove the lanes, or install with "
            "--profile lanes"
        )
    return "lanes"


def hooks_off(chosen: str) -> set:
    return set(LANE_HOOKS) if chosen == "solo" else set()
