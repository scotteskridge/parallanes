"""Shared test helpers: throwaway git repos with a kit config, and running the kit CLI."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "payload" / "kit-owned" / ".claude" / "kit" / "cli.py"

RULES_TOML = """
[project]
name = "demo"
test_command = "python -m pytest -q"
integration_branch = "main"

[[checks.rules]]
id = "no-print"
pattern = '\\bprint\\('
paths = ["src/**/*.py"]
exclude = ["src/cli/**"]
message = "Use the logger, not print()."
"""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout


def make_repo(base: Path, config: str = RULES_TOML, name: str = "my project", settings: bool = True) -> Path:
    """A git repo whose path contains a space, with .claude/kit.toml written.

    settings: also write the permission rules the config needs, as an installed project has them
    (otherwise `check all` reports the missing rules). Skipped when the config doesn't load.
    """
    repo = base / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "core.autocrlf", "false")
    if config is not None:
        write(repo, ".claude/kit.toml", config)
        if settings:
            sync_settings(repo)
    return repo


def sync_settings(repo: Path) -> None:
    from kitlib.config import ConfigError, load
    from kitlib.settings import apply_sync, plan_sync

    try:
        config = load(repo)
    except ConfigError:
        return  # a test of a broken config: nothing to generate
    apply_sync(repo, plan_sync(repo, config))


def write(repo: Path, rel: str, text: str) -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def run_cli(cwd: Path, *args: str, stdin: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=cwd,
        input=stdin,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def hook_payload(repo: Path, rel: str, tool: str = "Edit") -> str:
    return json.dumps(
        {
            "session_id": "test",
            "cwd": str(repo),
            "hook_event_name": "PostToolUse",
            "tool_name": tool,
            "tool_input": {"file_path": str(repo / rel)},
            "tool_response": {"success": True},
        }
    )
