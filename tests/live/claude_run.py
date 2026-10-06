"""Run a real `claude -p` session for a live check, and fail unless what it tests actually loaded.

Dev-only: never installed. `--bare` will become the default for `-p` and skips hooks, skills,
subagents, plugins and CLAUDE.md, with no flag to opt out; a live check that only pinned flags would
then pass while testing nothing. So every run states what it loads, and asserts it from the stream:
skills, agents and plugins from the `system/init` event, hooks from the `hook_started` events that
`--include-hook-events` adds (init doesn't list hooks). See docs/live-checks.md.
"""
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

CLAUDE_CONFIG = Path.home() / ".claude.json"


class LiveCheckError(AssertionError):
    """The run didn't happen as the check needs; its result says nothing about the kit."""


@dataclass
class Run:
    events: list
    init: dict
    result: dict

    def hooks_fired(self) -> list:
        return [event.get("hook_name") for event in self.events
                if event.get("type") == "system" and event.get("subtype") == "hook_started"]

    def denied_paths(self) -> list:
        """file_path (or command) of each call Claude Code refused, from the result's permission_denials."""
        return [denial.get("tool_input", {}).get("file_path") or denial.get("tool_input", {}).get("command")
                for denial in self.result.get("permission_denials", [])]


def scratch_project(name: str) -> Path:
    """A fixed folder per check, reused across runs, so the owner accepts its trust dialog once."""
    folder = Path(tempfile.gettempdir()) / "kit-live" / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def is_trusted(folder: Path, claude_config: Path = CLAUDE_CONFIG) -> bool:
    """Whether Claude Code has recorded the trust dialog as accepted for folder or a folder above it.
    Read only: the kit never writes the owner's Claude config."""
    try:
        projects = json.loads(claude_config.read_text(encoding="utf-8")).get("projects", {})
    except (OSError, ValueError):
        return False
    fold = str.lower if os.name == "nt" else str  # Windows paths ignore case; the keys vary
    trusted = {fold(key.rstrip("/")) for key, value in projects.items()
               if isinstance(value, dict) and value.get("hasTrustDialogAccepted") is True}
    path = Path(folder).resolve()
    return any(fold(candidate.as_posix()) in trusted for candidate in (path, *path.parents))


def run_claude(project: Path, prompt: str, *, permission_mode: str, model: str = "haiku",
               budget_usd: float = 1.0, max_turns: int | None = None, allowed_tools=(), disallowed_tools=(),
               extra_args=(), expect_skills=(), expect_agents=(), expect_plugins=(), expect_hooks=(),
               needs_trust: bool = False, claude_config: Path = CLAUDE_CONFIG,
               command=None, timeout: int = 600) -> Run:
    """One headless session in project. expect_hooks: `Event` or `Event:Matcher` names that must fire.
    needs_trust: agent frontmatter hooks (the reviewer's guard) are skipped in an untrusted folder."""
    if needs_trust and not is_trusted(project, claude_config):
        raise LiveCheckError(
            f"{project} isn't trusted, so agent frontmatter hooks would be skipped. Open Claude Code "
            f"there once and accept the trust dialog: cd \"{project}\" then run claude")
    if command is None:
        found = shutil.which("claude")
        if found is None:
            raise LiveCheckError("claude isn't on PATH; install Claude Code to run live checks")
        command = [found]
    args = [*command, "-p", prompt,
            # Everything that decides what loads, stated: personal ~/.claude settings stay out.
            "--output-format", "stream-json", "--verbose", "--include-hook-events",
            "--setting-sources", "project,local", "--permission-mode", permission_mode,
            "--model", model, "--max-budget-usd", str(budget_usd)]
    if max_turns is not None:
        args += ["--max-turns", str(max_turns)]
    for flag, tools in (("--allowedTools", allowed_tools), ("--disallowedTools", disallowed_tools)):
        if tools:
            args += [flag, *tools]
    args += list(extra_args)
    done = subprocess.run(args, cwd=project, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)
    if done.returncode != 0:
        raise LiveCheckError(f"claude -p failed (exit {done.returncode}): {done.stderr.strip() or done.stdout[-500:]}")
    events = [json.loads(line) for line in done.stdout.splitlines() if line.strip()]
    init = next((event for event in events if event.get("type") == "system" and event.get("subtype") == "init"), None)
    if init is None:
        raise LiveCheckError("no system/init event in the stream: can't tell what this session loaded")
    result = next((event for event in reversed(events) if event.get("type") == "result"), {})
    run = Run(events=events, init=init, result=result)
    _expect_loaded(run, expect_skills, expect_agents, expect_plugins, expect_hooks)
    return run


def _expect_loaded(run: Run, skills, agents, plugins, hooks) -> None:
    fired = run.hooks_fired()
    fired_events = {name.split(":", 1)[0] for name in fired if name}
    missing = {
        "skills not loaded": [name for name in skills if name not in run.init.get("skills", [])],
        "agents not loaded": [name for name in agents if name not in run.init.get("agents", [])],
        "plugins not loaded": [name for name in plugins
                               if name not in [plugin.get("name") for plugin in run.init.get("plugins", [])]],
        "hooks that didn't fire": [name for name in hooks if name not in fired and name not in fired_events],
    }
    lines = [f"{what}: {', '.join(names)}\n" for what, names in missing.items() if names]
    if lines:
        raise LiveCheckError(
            "this session didn't load what the check relies on, so its result would say nothing:\n"
            + "".join(lines)
            + f"(Claude Code {run.init.get('claude_code_version')}. Is `--bare` now the default for -p, "
            "is the folder untrusted, or is a file missing from the scratch project?)")
