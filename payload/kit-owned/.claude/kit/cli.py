"""The kit's command line: `kit check`, `kit hook`, `kit settings`, `kit changelog`.

Run from anywhere inside a project: `python .claude/kit/cli.py <command>` (or the shim the installer
sets up). Exit codes. CLI: 0 clean, 1 findings, 2 usage or config error. Hook mode follows Claude
Code's protocol instead: 0 nothing to report, 2 findings for Claude to fix, 1 a kit error that
is shown but never blocks the edit (decision 9). The protected hook is the exception: it fails
closed, so every error is an exit 2 (decision 33).
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kitlib import changelog, gitfiles, protected, rules_check  # noqa: E402
from kitlib.config import ConfigError, ConfigMissing, find_root, load  # noqa: E402
from kitlib.findings import format_findings  # noqa: E402
from kitlib.globs import normalize  # noqa: E402

OK, FINDINGS, USAGE = 0, 1, 2
HOOK_OK, HOOK_ERROR, HOOK_BLOCK = 0, 1, 2

CHECKS = ("rules", "protected")


class UsageError(Exception):
    pass


def main(argv=None) -> int:
    # Findings can contain any text; a Windows console or pipe would otherwise crash on it.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:
        # In hook mode, exit 2 would send usage text to Claude after every edit: report it
        # as a non-blocking hook error instead (a typo in settings.json, decision 9).
        # PreToolUse is the protected guard's event: there, fail closed instead (decision 33).
        if argv[:1] == ["hook"] and stop.code == USAGE:
            return HOOK_BLOCK if _hook_event() == "PreToolUse" else HOOK_ERROR
        raise
    if not hasattr(args, "run"):
        parser.print_help()
        return USAGE
    return args.run(args)


def _hook_event() -> str | None:
    """The hook_event_name Claude Code sent on stdin, or None if it can't be read."""
    try:
        payload = json.loads(sys.stdin.read())
    except (ValueError, OSError):
        return None
    return payload.get("hook_event_name") if isinstance(payload, dict) else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kit", description="claude-code-lanes-starter project tools.")
    commands = parser.add_subparsers(title="commands")

    check = commands.add_parser("check", help="run the project's checks on files")
    check.add_argument("name", choices=[*CHECKS, "all"], help="which check to run")
    source = check.add_mutually_exclusive_group()
    source.add_argument("--staged", action="store_true", help="check what is staged for commit")
    source.add_argument("--diff", metavar="BASE", help="check files changed since BASE (e.g. origin/main)")
    check.add_argument("files", nargs="*", help="files to check (default: every tracked file)")
    check.set_defaults(run=run_check)

    hook = commands.add_parser("hook", help="Claude Code hook entry points (JSON on stdin)")
    hook.add_argument("name", choices=["rules-check", "protected"])
    hook.set_defaults(run=run_hook)

    log = commands.add_parser("changelog", help="changelog fragments")
    log_commands = log.add_subparsers(title="changelog commands")
    build = log_commands.add_parser("build", help="compile docs/changelog.d/ into docs/CHANGELOG.md")
    build.add_argument("--version", required=True, help="release version, e.g. 1.2.0")
    build.add_argument("--date", default=datetime.date.today().isoformat(), help="release date (default: today)")
    build.add_argument("--dry-run", action="store_true", help="print the new section; change nothing")
    build.set_defaults(run=run_changelog_build)
    return parser


# ---- kit check -------------------------------------------------------------------------------

def run_check(args) -> int:
    names = list(CHECKS) if args.name == "all" else [args.name]
    try:
        root = find_root(Path.cwd())
        config = load(root)
        findings = []
        if "rules" in names:
            findings += rules_check.check(config, collect_files(root, config, args))
        if "protected" in names:
            findings += check_protected(root, config, args)
    except (ConfigError, gitfiles.GitError, UsageError) as error:
        print(f"kit: {error}", file=sys.stderr)
        return USAGE
    if findings:
        print(format_findings(findings))
        print(f"\n{len(findings)} finding(s). Rules live in .claude/kit.toml.", file=sys.stderr)
        return FINDINGS
    return OK


def check_protected(root: Path, config, args) -> list:
    """Changes to protected paths. A whole-project run has no change to judge, so it checks nothing."""
    if args.staged:
        paths = gitfiles.touched_staged(root)
    elif args.diff:
        paths = gitfiles.touched_since(root, args.diff)
    elif args.files:
        paths = explicit_paths(root, args.files)
    else:
        return []
    findings = protected.check(config, paths)
    if findings and protected.allowed_by_human():
        print(
            f"kit: {len(findings)} protected path change(s) allowed by {protected.ALLOW_VARIABLE}=1.",
            file=sys.stderr,
        )
        return []
    return findings


def explicit_paths(root: Path, names) -> list[str]:
    # `vendor\a.py` means the same file on every platform, as in kit.toml globs.
    paths = [relative_to_root(root, Path(normalize(name))) for name in names]
    for name, path in zip(names, paths):
        if not (root / path).is_file():
            raise UsageError(f"{name}: not a file")  # a typo must not pass as "clean"
    return paths


def collect_files(root: Path, config, args):
    """(project-relative path, text) for each file some rule covers; binary files are skipped.

    Paths are filtered before anything is read, so large repos only pay for covered files.
    """
    if args.staged:
        for path in gitfiles.staged(root):
            if not rules_check.covered(config, path):
                continue
            text = gitfiles.read_staged(root, path)
            if text is not None:
                yield path, text
        return
    if args.diff:
        paths = gitfiles.changed_since(root, args.diff)
    elif args.files:
        paths = explicit_paths(root, args.files)
    else:
        paths = gitfiles.tracked(root)
    for path in paths:
        if not rules_check.covered(config, path):
            continue
        text = gitfiles.read_worktree(root, path)
        if text is not None:
            yield path, text


def relative_to_root(root: Path, path: Path) -> str:
    absolute = (Path.cwd() / path).resolve()
    try:
        return absolute.relative_to(root.resolve()).as_posix()
    except ValueError:
        raise UsageError(f"{path} is outside the project ({root})") from None


# ---- kit hook ----------------------------------------------------------------------------------

def run_hook(args) -> int:
    if args.name == "protected":
        return run_hook_protected()
    # rules-check fails open: any problem with the kit itself is reported (exit 1) and never blocks.
    try:
        return hook_rules_check(json.loads(sys.stdin.read()))
    except Exception as error:  # noqa: BLE001 - the hook must never crash with a traceback
        print(f"kit hook {args.name}: {type(error).__name__}: {error}", file=sys.stderr)
        return HOOK_ERROR


def run_hook_protected() -> int:
    """PreToolUse backstop. Fails closed: in PreToolUse only exit 2 blocks, so every error exits 2."""
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("hook input is not a JSON object")
        root = find_root(Path(payload.get("cwd") or os.getcwd()))
        try:
            config = load(root)
        except ConfigMissing:
            return HOOK_OK  # the kit isn't set up here: nothing to enforce (decision 33)
        reason = protected.check_tool_call(payload, root, config)
    except ConfigError as error:
        print(
            f"Blocked: the kit's protected-paths guard can't read its config: {error}\n"
            "Fix .claude/kit.toml (or ask the user to) before running commands or editing files.",
            file=sys.stderr,
        )
        return HOOK_BLOCK
    except Exception as error:  # noqa: BLE001 - fail closed, without a traceback
        print(
            f"Blocked: the kit's protected-paths guard failed ({type(error).__name__}: {error}).\n"
            "Tell the user; this is a bug in the kit or its install, not something to work around.",
            file=sys.stderr,
        )
        return HOOK_BLOCK
    if reason is None:
        return HOOK_OK
    print(
        f"Blocked by the kit's protected-paths guard: {reason}.\n"
        "Don't look for another way to do this. If it is needed, ask the user to do it themselves "
        "or to change .claude/kit.toml.",
        file=sys.stderr,
    )
    return HOOK_BLOCK


def hook_rules_check(payload: dict) -> int:
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not file_path:
        return HOOK_OK
    cwd = Path(payload.get("cwd") or os.getcwd())
    root = find_root(cwd)
    try:
        config = load(root)
    except ConfigMissing:
        return HOOK_OK  # the kit isn't set up here: nothing to enforce
    except ConfigError as error:
        print(f"kit: rules not checked: {error}", file=sys.stderr)
        return HOOK_ERROR

    try:
        rel = (cwd / file_path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return HOOK_OK  # outside the project
    if not rules_check.covered(config, rel):
        return HOOK_OK
    text = gitfiles.read_worktree(root, rel)
    if text is None:
        return HOOK_OK  # deleted or binary
    findings = rules_check.check(config, [(rel, text)])
    if not findings:
        return HOOK_OK
    print(
        f"Rule violations in {rel} (rules from .claude/kit.toml):\n{format_findings(findings)}\n"
        "Fix the file. If a rule looks wrong, tell the user instead of working around it.",
        file=sys.stderr,
    )
    return HOOK_BLOCK


# ---- kit changelog -------------------------------------------------------------------------------

def run_changelog_build(args) -> int:
    root = find_root(Path.cwd())
    try:
        release = changelog.build(root, args.version, args.date)
    except changelog.ChangelogError as error:
        print(f"kit: {error}", file=sys.stderr)
        return USAGE
    if args.dry_run:
        print(release.section, end="")
        return OK
    changelog.apply(root, release)
    print(f"Released {args.version}: {len(release.fragments)} fragment(s) compiled into docs/CHANGELOG.md.")
    return OK


if __name__ == "__main__":
    sys.exit(main())
