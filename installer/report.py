"""What the installer prints: the plan before writing, and the next steps after (plan 08)."""

import subprocess
import sys
import tomllib
from pathlib import Path

from . import plan as file_plan
from .values import KIT_COMMAND, QUESTIONS


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


def answers(used: dict | None, precommit: str | None, profile: str | None, detected: bool) -> None:
    """The answers the files are made from: what a person most wants to check (trial F1).

    used None: a re-run, whose saved answers aren't shown (decision 113). profile: shown when it is
    new or changed (decision 121).
    """
    print("\nAnswers:")
    for key, question in QUESTIONS if used else ():
        print(f"  {question}: {used[key] or '(none)'}")
    if profile is not None:
        print(f"  Profile: {profile}")
    if precommit is not None:  # asked only at a repository's root
        print(f"  Pre-commit check: {precommit}")
    if detected:
        print(
            "  (detected defaults: a real run without --yes asks for each)"
            if used
            else "  (assumed: a real run without --yes asks this)"
        )


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
    for name in settings["profile_hooks"]:
        print(f"  note     the {name} hook is added for the lanes profile")
    for name in settings["profile_removed_hooks"]:
        print(f"  note     the {name} hook is removed for the solo profile")
    for name in settings["removed_hooks"]:
        print(
            f"  note     the {name} hook is switched off in .claude/kit.toml and is removed from .claude/settings.json"
        )
    for name in settings["still_running"]:
        where = "by the solo profile" if name in settings["profile_off"] else "in .claude/kit.toml"
        print(
            f"  note     the {name} hook is switched off {where} but .claude/settings.json still "
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


def next_steps(target: Path, files: file_plan.FilePlan, precommit: str, done: dict) -> None:
    """done: what the install did beyond its files (plan 16): profile, lanes, guess, committed,
    created, origin. The steps leave out what's done and name what's left."""
    steps = [
        f"Open Claude Code in {target} once and accept the folder trust dialog: until you do, the "
        "reviewer agent runs without its read-only guard.",
    ]
    kit_new = [w.rel for w in files.writes if w.kind == "kit-new"]
    if kit_new:
        steps.append("Compare each .kit-new file with yours, take what you want, then delete it: " + ", ".join(kit_new))
    # From the files, not the answers: the owner may have fixed them since the last run.
    if not _project_value(target, "test_command"):
        steps.append("Set test_command in .claude/kit.toml: tasks can't finish without it.")
    agents = target / "AGENTS.md"
    if agents.is_file() and "TODO:" in agents.read_text(encoding="utf-8", errors="replace"):
        steps.append("Replace the TODO lines in AGENTS.md.")
    kind = precommit.partition(":")[0]
    if kind == "no-repo":
        # The branch named, not git's default: `git init` may make master while lanes look for main.
        branch = _project_value(target, "integration_branch") or "main"
        steps.append(
            f"Not a git repository yet: run `git init -b {branch}`, commit, then `git config core.hooksPath .githooks`."
        )
    elif kind == "subfolder":
        steps.append("This folder is not the root of its git repository: the kit's lanes and checks expect to be.")
    elif kind == "own-hooks":
        steps.append("To run the kit's pre-commit check, call `sh .githooks/pre-commit` from your own pre-commit hook.")
    if not done["committed"]:
        if sys.platform == "win32":
            steps.append(
                "Commit the kit's files; mark the pre-commit hook executable for macOS/Linux clones with "
                "`git add --chmod=+x .githooks/pre-commit`."
            )
        else:
            steps.append("Commit the kit's files (python-path stays out: it's this machine's).")
    steps += _lane_steps(target, done)
    # The kit can't change the repo's GitHub settings, and until both jobs are required a red run
    # doesn't stop a merge (plan 09). A project that kept its own kit.yml has the kit's beside it.
    workflow = ".github/workflows/kit.yml"
    if f"{workflow}.kit-new" in kit_new:
        steps.append(
            f"Compare {workflow}.kit-new with your {workflow}: the kit's CI runs `parallanes check all` and "
            "`parallanes test`. "
            'Whichever you keep, make its jobs required checks: docs/ai/protected-paths.md, "The server".'
        )
    else:
        steps.append(
            f"Push to GitHub, add your stack's setup to {workflow}, then make its kit-checks and tests jobs "
            'required checks: docs/ai/protected-paths.md, "The server".'
        )
    print("\nNext:")
    for number, step in enumerate(steps, start=1):
        print(f"  {number}. {step}")


def _lane_steps(target: Path, done: dict) -> list:
    create = f"`{KIT_COMMAND} lanes create`"
    if done["profile"] == "solo":
        return ["For several agents at once later, re-run the installer with `--profile lanes`."]
    folders = _lane_folders(target) if done["lanes"] else []
    if folders and all(exists for _, exists in folders):  # made now, or on an earlier run (review round 1)
        # Folders only: `cd x && claude` doesn't parse in Windows PowerShell 5.1.
        shown = "".join(f"\n       {folder}" for folder, _ in folders)
        return [
            "Open one Claude Code session in each lane's folder (`cd` there, then `claude`; not "
            f"`claude --worktree`), and start a task with `{KIT_COMMAND} lanes start <task>`:{shown}"
        ]
    if done["lanes"]:
        if done["origin"]:
            return [f"Push the kit's commit to origin, then run {create}: new lanes start from what origin has."]
        if done["committed"]:
            return [f"Run {create}."]
        return [f"Once the kit's files are committed, run {create}."]
    why = done["guess"].get("why")
    found = f"No lanes were guessed ({why}). " if why else ""
    return [
        f"{found}Add [[lanes]] tables to .claude/kit.toml (`{KIT_COMMAND} lanes suggest` prints a guess; "
        f"docs/ai/parallel-lanes.md explains them), commit, then run {create}."
    ]


def _lane_folders(target: Path) -> list:
    """(folder as shown, whether it exists) per lane: relative to the project when inside it."""
    from kitlib import config as kit_config
    from kitlib import lanes

    config = kit_config.load(target)
    folders = []
    for lane in config.lanes:
        folder = lanes.lane_folder(target, config, lane)
        try:
            shown = folder.resolve().relative_to(target.resolve()).as_posix()
        except ValueError:  # worktree_root outside the project, e.g. "../{project}-lanes"
            shown = str(folder)
        folders.append((shown, folder.is_dir()))
    return folders


def _project_value(target: Path, key: str) -> str:
    try:
        config = tomllib.loads((target / ".claude" / "kit.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(config.get("project", {}).get(key, "")).strip()
