"""`kit_setup.py`: install the kit into a project (plan 08). Run by `install.ps1` / `install.sh`.

The order matters: ask, then plan everything (files, settings, pre-commit), print the plan, and
only then write. Any problem found while planning stops the install with nothing written.
"""

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path

from kitlib import config as kit_config
from kitlib import render
from kitlib import settings as kit_settings

from . import blocks, plan, settings_hooks, values

MANIFEST_REL = ".claude/kit/manifest.json"
PYTHON_PATH_REL = ".claude/kit/python-path"
HOOKS_PATH = ".githooks"


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    target = Path(args.target).absolute()
    print(f"Installing claude-code-lanes-starter into {target}")
    print(f"Python: {sys.executable}")
    previous = _read_json(target / MANIFEST_REL)
    defaults = values.detect(target, previous.get("values", {}))
    is_repo = (target / ".git").exists()
    try:
        answers = defaults if args.yes else {**defaults, **values.ask(defaults)}
        want_precommit = is_repo and (args.yes or values.confirm("Run the kit's checks before each commit?", True))
    except EOFError:
        print("kit setup: no answer (input closed); run with --yes to take the defaults", file=sys.stderr)
        return 2
    answers["kit_version"] = _kit_version()

    try:
        files = plan.build(target, answers, previous)
        settings_change = _plan_settings(target, files, previous)
    except (
        blocks.BlockError,
        kit_config.ConfigError,
        kit_settings.SettingsError,
        settings_hooks.HooksError,
        render.TemplateError,
    ) as error:
        print(f"kit setup: stopped, nothing written: {error}", file=sys.stderr)
        return 2
    precommit = _plan_precommit(target, is_repo, want_precommit)
    python_path = f"{sys.executable}\n".encode()
    manifest = _manifest(answers, files, settings_change["hooks"])

    _print_plan(target, files, settings_change, precommit)
    if args.dry_run:
        print("\nDry run: nothing was written.")
        return 0

    target.mkdir(parents=True, exist_ok=True)
    plan.apply(target, files)
    settings_change["apply"]()
    _write_if_changed(target / PYTHON_PATH_REL, python_path)
    _write_if_changed(target / MANIFEST_REL, manifest)
    if precommit == "set":
        subprocess.run(["git", "config", "core.hooksPath", HOOKS_PATH], cwd=target, check=True)
    _print_next_steps(target, files, answers, precommit)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kit_setup.py", description="Install the kit into a project.")
    parser.add_argument("--target", default=".", help="the project folder (default: the current folder)")
    parser.add_argument("--dry-run", action="store_true", help="print what would be written, write nothing")
    parser.add_argument("--yes", action="store_true", help="take every detected default without asking")
    return parser


def _kit_version() -> str:
    pyproject = plan.PAYLOAD.parent / "pyproject.toml"
    return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError):
        return {}  # a broken manifest only loses re-run memory: every kit file is then treated as edited
    return data if isinstance(data, dict) else {}


def _plan_settings(target: Path, files: plan.FilePlan, previous: dict) -> dict:
    """Deny and ask rules from the kit.toml in effect (the owner's if they kept one), plus the hooks."""
    existing = target / ".claude" / "kit.toml"
    if existing.is_file():
        text = existing.read_text(encoding="utf-8")
    else:
        text = next(w.data for w in files.writes if w.rel == ".claude/kit.toml").decode("utf-8")
    sync = kit_settings.plan_sync(target, kit_config.parse(text))
    before = json.dumps(kit_settings.read_json(target / kit_settings.SETTINGS_REL, "settings.json"), sort_keys=True)
    record = settings_hooks.merge(sync.settings, previous.get("hooks", []))
    changed = json.dumps(sync.settings, sort_keys=True) != before
    added_hooks = len([e for e in record if e not in previous.get("hooks", [])])

    def apply():
        if changed:
            kit_settings.write_json(target / kit_settings.SETTINGS_REL, sync.settings, sync.style)
        if sync.record_changed or sync.settings_changed:
            kit_settings.write_json(target / kit_settings.RECORD_REL, sync.record, kit_settings.Style())

    rules = sum(len(added) for added in sync.added.values())
    return {"changed": changed, "rules": rules, "added_hooks": added_hooks, "hooks": record, "apply": apply}


def _plan_precommit(target: Path, is_repo: bool, wanted: bool) -> str:
    if not is_repo:
        return "no-repo"
    if not wanted:
        return "declined"
    result = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=target, capture_output=True, text=True)
    current = result.stdout.strip()
    if current == HOOKS_PATH:
        return "already"
    return "other:" + current if current else "set"


def _manifest(answers: dict, files: plan.FilePlan, hooks: list) -> bytes:
    data = {
        "kit_version": answers["kit_version"],
        "values": {key: answers[key] for key in sorted(answers) if key != "kit_version"},
        "files": dict(sorted(files.files.items())),
        "templates": sorted(files.templates),
        "hooks": hooks,
    }
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _write_if_changed(path: Path, data: bytes) -> None:
    if not path.is_file() or path.read_bytes() != data:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _print_plan(target: Path, files: plan.FilePlan, settings_change: dict, precommit: str) -> None:
    print()
    for write in files.writes:
        note = f"  ({write.note})" if write.note else ""
        print(f"  {write.kind:<8} {write.rel}{note}")
    if settings_change["changed"]:
        print(
            f"  settings .claude/settings.json  (+{settings_change['rules']} permission rules, "
            f"+{settings_change['added_hooks']} hooks; your entries are kept)"
        )
    if files.unchanged or files.kept:
        print(f"  {len(files.unchanged)} files already up to date; {len(files.kept)} project files left as they are")
    messages = {
        "set": "git config core.hooksPath .githooks (the pre-commit check)",
        "already": "",
        "declined": "pre-commit check not turned on (you said no)",
        "no-repo": "pre-commit check not turned on: not a git repository",
    }
    message = messages.get(precommit, f"pre-commit check not turned on: core.hooksPath is already {precommit[6:]!r}")
    if message:
        print(f"  {message}")


def _print_next_steps(target: Path, files: plan.FilePlan, answers: dict, precommit: str) -> None:
    steps = [
        f"Open Claude Code in {target} once and accept the folder trust dialog: until you do, the "
        "reviewer agent runs without its read-only guard.",
    ]
    kit_new = [w.rel for w in files.writes if w.kind == "kit-new"]
    if kit_new:
        steps.append("Compare each .kit-new file with yours, take what you want, then delete it: " + ", ".join(kit_new))
    if not answers["test_command"]:
        steps.append("Set test_command in .claude/kit.toml: tasks can't finish without it.")
    if answers["project_description"] == values.TODO_DESCRIPTION or answers["stack"] == values.TODO_STACK:
        steps.append("Replace the TODO lines in AGENTS.md.")
    if precommit == "no-repo":
        steps.append("Not a git repository yet: run `git init`, then `git config core.hooksPath .githooks`.")
    steps.append(
        "For parallel lanes, add [[lanes]] tables to .claude/kit.toml (docs/ai/parallel-lanes.md), then run "
        f"`{values.KIT_COMMAND} lanes create`."
    )
    steps.append("Commit the kit's files (python-path stays out: it's this machine's).")
    print("\nNext:")
    for number, step in enumerate(steps, start=1):
        print(f"  {number}. {step}")
