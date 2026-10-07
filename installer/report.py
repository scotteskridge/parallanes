"""What the installer prints: the plan before writing, and the next steps after (plan 08)."""

import subprocess
import sys
import tomllib
from pathlib import Path

from . import plan as file_plan
from .values import KIT_COMMAND


def repo_root(target: Path) -> Path | None:
    """The git repository the target is in, or None. The target may not exist yet."""
    folder = target
    while not folder.exists():
        if folder.parent == folder:  # main.py refuses a missing drive first; never loop on one
            return None
        folder = folder.parent
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=folder, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    root = Path(result.stdout.strip())
    return target if target.exists() and root.resolve() == target.resolve() else root


def plan(files: file_plan.FilePlan, settings: dict, extra: dict, precommit: str) -> None:
    print()
    for write in files.writes:
        note = f"  ({write.note})" if write.note else ""
        print(f"  {write.kind:<8} {write.rel}{note}")
    if settings["changed"]:
        print(
            f"  settings .claude/settings.json  (+{settings['rules']} permission rules, "
            f"+{settings['added_hooks']} hooks; your entries are kept)"
        )
    for name in settings["readded_hooks"]:
        how = (
            "it is the security backstop and can't be switched off"
            if name == "protected"
            else "to keep it out, set it false under [hooks] in .claude/kit.toml"
        )
        print(f"  note     the {name} hook isn't in .claude/settings.json and is added; {how}")
    for name in settings["switched_on_hooks"]:
        print(f"  note     the {name} hook is on in .claude/kit.toml and is added to .claude/settings.json")
    for name in settings["removed_hooks"]:
        print(
            f"  note     the {name} hook is switched off in .claude/kit.toml and is removed from .claude/settings.json"
        )
    for name in settings["still_running"]:
        print(
            f"  note     the {name} hook is switched off in .claude/kit.toml but .claude/settings.json still "
            "runs your copy of it; remove that yourself"
        )
    if settings["writes_record"]:
        print("  write    .claude/kit/generated-rules.json  (the rules the kit wrote)")
    for rel in extra:
        print(f"  write    {rel}")
    for note in files.notes:
        print(f"  note     {note}")
    if files.unchanged or files.kept:
        print(f"  {len(files.unchanged)} files already up to date; {len(files.kept)} project files left as they are")
    message = _precommit_message(precommit)
    if message:
        print(f"  {message}")


def _precommit_message(precommit: str) -> str:
    kind, _, detail = precommit.partition(":")
    return {
        "set": "git config core.hooksPath .githooks (the pre-commit check)",
        "already": "",
        "declined": "pre-commit check not turned on (you said no)",
        "no-repo": "pre-commit check not turned on: not a git repository",
        "subfolder": "pre-commit check not turned on: this folder is not the root of its git repository",
        "other": f"pre-commit check not turned on: core.hooksPath is already {detail!r}",
        "own-hooks": f"pre-commit check not turned on: it would switch off your hooks in .git/hooks ({detail})",
        "unknown": "pre-commit check not turned on: git couldn't say where this repository's hooks are",
    }[kind]


def next_steps(target: Path, files: file_plan.FilePlan, precommit: str) -> None:
    steps = [
        f"Open Claude Code in {target} once and accept the folder trust dialog: until you do, the "
        "reviewer agent runs without its read-only guard.",
    ]
    kit_new = [w.rel for w in files.writes if w.kind == "kit-new"]
    if kit_new:
        steps.append("Compare each .kit-new file with yours, take what you want, then delete it: " + ", ".join(kit_new))
    # From the files, not the answers: the owner may have fixed them since the last run.
    if not _test_command(target):
        steps.append("Set test_command in .claude/kit.toml: tasks can't finish without it.")
    agents = target / "AGENTS.md"
    if agents.is_file() and "TODO:" in agents.read_text(encoding="utf-8", errors="replace"):
        steps.append("Replace the TODO lines in AGENTS.md.")
    kind = precommit.partition(":")[0]
    if kind == "no-repo":
        steps.append("Not a git repository yet: run `git init`, then `git config core.hooksPath .githooks`.")
    elif kind == "subfolder":
        steps.append("This folder is not the root of its git repository: the kit's lanes and checks expect to be.")
    elif kind == "own-hooks":
        steps.append("To run the kit's pre-commit check, call `sh .githooks/pre-commit` from your own pre-commit hook.")
    steps.append(
        "For parallel lanes, add [[lanes]] tables to .claude/kit.toml (docs/ai/parallel-lanes.md), then run "
        f"`{KIT_COMMAND} lanes create`."
    )
    if sys.platform == "win32":
        steps.append(
            "Commit the kit's files; mark the pre-commit hook executable for macOS/Linux clones with "
            "`git add --chmod=+x .githooks/pre-commit`."
        )
    else:
        steps.append("Commit the kit's files (python-path stays out: it's this machine's).")
    print("\nNext:")
    for number, step in enumerate(steps, start=1):
        print(f"  {number}. {step}")


def _test_command(target: Path) -> str:
    try:
        config = tomllib.loads((target / ".claude" / "kit.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(config.get("project", {}).get("test_command", "")).strip()
