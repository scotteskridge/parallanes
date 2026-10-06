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

from . import plan, report, settings_hooks, values

MANIFEST_REL = ".claude/kit/manifest.json"
PYTHON_PATH_REL = ".claude/kit/python-path"
HOOKS_PATH = ".githooks"
STOPS = (
    plan.PlanError,
    kit_config.ConfigError,
    kit_settings.SettingsError,
    settings_hooks.HooksError,
    render.TemplateError,
)


class ManifestError(ValueError):
    """manifest.json can't be trusted; without it a re-run could overwrite the owner's files."""


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    target = Path(args.target).absolute()
    try:
        _check_target(target)
        previous = read_manifest(target)
    except (ManifestError, plan.PlanError) as error:
        return _stop(error)
    print(f"Installing claude-code-lanes-starter into {target}")
    print(f"Python: {sys.executable}")
    repo = report.repo_root(target)
    answers = values.detect(target, previous.get("values", {}))
    saved = previous.get("values", {})
    try:
        if saved:
            # A re-run renders the same files from the same answers.
            print("Using the answers from the earlier install (.claude/kit/manifest.json).")
        elif not args.yes:
            answers.update(values.ask(answers))
        # The pre-commit answer is saved only once it was given (or --yes at a repo root), so a re-run
        # never undoes a "no", and a folder that only now became a repo is still asked.
        precommit_answer = saved.get("precommit")
        if precommit_answer is None and repo == target:
            yes = args.yes or values.confirm("Run the kit's checks before each commit?", True)
            precommit_answer = "yes" if yes else "no"
    except EOFError:
        return _stop("no answer (input closed); run with --yes to take the defaults")
    if precommit_answer is not None:
        answers["precommit"] = precommit_answer
    want_precommit = repo == target and precommit_answer == "yes"
    answers["kit_version"] = _kit_version()

    try:
        files = plan.build(target, answers, previous)
        settings_change = _plan_settings(target, files, previous)
        for rel in (PYTHON_PATH_REL, MANIFEST_REL):
            plan.check_path(target, rel)
    except STOPS as error:
        return _stop(error)
    precommit = _plan_precommit(target, repo, want_precommit)
    extra = {
        PYTHON_PATH_REL: f"{sys.executable}\n".encode(),
        MANIFEST_REL: _manifest(answers, files, settings_change["hooks"]),
    }
    extra = {rel: data for rel, data in extra.items() if _read(target / rel) != data}

    report.plan(files, settings_change, extra, precommit)
    if args.dry_run:
        print("\nDry run: nothing was written.")
        return 0

    target.mkdir(parents=True, exist_ok=True)
    plan.apply(target, files)
    settings_change["apply"]()
    for rel, data in extra.items():
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        (target / rel).write_bytes(data)
    if precommit == "set":
        subprocess.run(["git", "config", "core.hooksPath", HOOKS_PATH], cwd=target, check=True)
    report.next_steps(target, files, precommit)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kit_setup.py", description="Install the kit into a project.")
    parser.add_argument("--target", default=".", help="the project folder (default: the current folder)")
    parser.add_argument("--dry-run", action="store_true", help="print what would be written, write nothing")
    parser.add_argument("--yes", action="store_true", help="take every detected default without asking")
    return parser


def _stop(error) -> int:
    print(f"kit setup: stopped, nothing written: {error}", file=sys.stderr)
    return 2


def _check_target(target: Path) -> None:
    if not Path(target.anchor).exists():
        raise plan.PlanError(f"{target}: its drive or share {target.anchor} doesn't exist")
    if target.exists() and not target.is_dir():
        raise plan.PlanError(f"{target} is not a folder")
    if target.exists() and target.resolve() == plan.PAYLOAD.parent.resolve():
        raise plan.PlanError(f"{target} is the kit's own repository; pass --target <your project folder>")


def _kit_version() -> str:
    pyproject = plan.PAYLOAD.parent / "pyproject.toml"
    return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]


def _read(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def _strings(value) -> bool:
    return all(isinstance(item, str) for item in value)


_MANIFEST_SHAPE = {
    "values": lambda v: isinstance(v, dict) and _strings(v.values()),
    "files": lambda v: isinstance(v, dict) and _strings(v.values()),
    "offered": lambda v: isinstance(v, dict) and _strings(v.values()),
    "templates": lambda v: isinstance(v, list) and _strings(v),
    "hooks": lambda v: isinstance(v, list),  # entries are checked by settings_hooks
}


def read_manifest(target: Path) -> dict:
    """The earlier install's record, or {} if there was none. A broken one stops the install: it is
    what keeps a re-run from overwriting the owner's files and duplicating hooks."""
    path = target / MANIFEST_REL
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as error:
        raise ManifestError(f"{MANIFEST_REL} can't be read ({error}); fix it or delete it") from None
    if not isinstance(data, dict):
        raise ManifestError(f"{MANIFEST_REL}: expected a JSON object; fix it or delete it")
    for key, valid in _MANIFEST_SHAPE.items():
        if key in data and not valid(data[key]):
            raise ManifestError(f"{MANIFEST_REL}: {key!r} has the wrong shape; fix it or delete it")
    try:
        settings_hooks.merge({}, data.get("hooks", []))  # checks the entries' shape
    except settings_hooks.HooksError as error:
        raise ManifestError(f"{error}; fix it or delete it") from None
    return data


def _plan_settings(target: Path, files: plan.FilePlan, previous: dict) -> dict:
    """Deny and ask rules from the kit.toml in effect (the owner's if they kept one), plus the hooks."""
    existing = target / ".claude" / "kit.toml"
    if existing.is_file():
        try:
            text = existing.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise kit_config.ConfigError(".claude/kit.toml: not UTF-8 text") from None
    else:
        text = next(w.data for w in files.writes if w.rel == ".claude/kit.toml").decode("utf-8")
    for rel in (kit_settings.SETTINGS_REL, kit_settings.RECORD_REL):
        plan.check_path(target, rel.as_posix())
    sync = kit_settings.plan_sync(target, kit_config.parse(text))
    before = json.dumps(kit_settings.read_json(target / kit_settings.SETTINGS_REL, "settings.json"), sort_keys=True)
    old_record = previous.get("hooks", [])
    record = settings_hooks.merge(sync.settings, old_record)
    changed = json.dumps(sync.settings, sort_keys=True) != before
    writes_record = sync.record_changed or sync.settings_changed

    def apply():
        if changed:
            kit_settings.write_json(target / kit_settings.SETTINGS_REL, sync.settings, sync.style)
        if writes_record:
            kit_settings.write_json(target / kit_settings.RECORD_REL, sync.record, kit_settings.Style())

    return {
        "changed": changed,
        "writes_record": writes_record,
        "rules": sum(len(added) for added in sync.added.values()),
        "added_hooks": len([entry for entry in record if entry not in old_record]),
        "hooks": record,
        "apply": apply,
    }


def _plan_precommit(target: Path, repo: Path | None, wanted: bool) -> str:
    if repo is None:
        return "no-repo"
    if repo != target:
        return "subfolder"
    if not wanted:
        return "declined"
    current = _git(target, "config", "--get", "core.hooksPath")
    if current == HOOKS_PATH:
        return "already"
    if current:
        return "other:" + current
    # core.hooksPath replaces .git/hooks entirely: the owner's own hooks there would stop running.
    hooks_rel = _git(target, "rev-parse", "--git-path", "hooks")
    hooks = target / hooks_rel
    own = []
    if hooks_rel and hooks.is_dir():  # "" would be the project folder itself
        own = sorted(path.name for path in hooks.iterdir() if path.is_file() and not path.name.endswith(".sample"))
    return "own-hooks:" + ", ".join(own) if own else "set"


def _git(target: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=target, capture_output=True, text=True)
    return result.stdout.strip()


def _manifest(answers: dict, files: plan.FilePlan, hooks: list) -> bytes:
    data = {
        "kit_version": answers["kit_version"],
        "values": {key: answers[key] for key in sorted(answers) if key != "kit_version"},
        "files": dict(sorted(files.files.items())),
        "templates": sorted(files.templates),
        "offered": dict(sorted(files.offered.items())),
        "hooks": hooks,
    }
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
