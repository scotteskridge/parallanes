"""Shared test helpers: throwaway git repos with a kit config, and running the kit CLI."""
import json
import re
import shutil
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
    # A copy of one empty repo made per test process: `git init` plus three config calls cost ~0.15 s
    # on Windows, copying the empty .git a few milliseconds. It holds no paths, so a copy is exact.
    shutil.copytree(_empty_git(), repo / ".git")
    if config is not None:
        write(repo, ".claude/kit.toml", config)
        if settings:
            sync_settings(repo)
    return repo


CACHE = {}  # "root": this test process's folder for built-once fixtures, set by conftest


def cache_root() -> Path:
    if "root" not in CACHE:
        raise RuntimeError("the fixture cache is set up by tests/conftest.py; run these helpers under pytest")
    return CACHE["root"]


def _empty_git() -> Path:
    if "git" not in CACHE:
        folder = cache_root() / "empty repo"
        folder.mkdir()
        git(folder, "init", "-q", "-b", "main")
        git(folder, "config", "user.name", "Test")
        git(folder, "config", "user.email", "test@example.com")
        git(folder, "config", "core.autocrlf", "false")
        CACHE["git"] = folder / ".git"
    return CACHE["git"]


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


def frontmatter(path: Path) -> dict:
    """Single-line `key: value` fields. Skills here keep allowed-tools on one line (space-separated)."""
    match = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", path.read_text(encoding="utf-8"), re.DOTALL)
    assert match, f"{path} has no frontmatter"
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"')
    return fields
