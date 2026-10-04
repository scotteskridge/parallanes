"""Throwaway projects with lanes: a main checkout (path with spaces) and a bare `origin`."""
import json
import os
import sys
from pathlib import Path

from helpers import RULES_TOML, git, make_repo, write

LANES_TOML = RULES_TOML + """
[[lanes]]
name = "core"
scope = "Domain logic and its tests"
owns = ["src/core/**", "tests/core/**"]
resources = { dev_port = 8001 }

[[lanes]]
name = "api"
scope = "HTTP layer"
owns = ["src/api/**"]
"""


def lanes_repo(base: Path, config: str = LANES_TOML, origin: bool = True, ignore: bool = True) -> Path:
    """A committed project with lanes; origin/main exists when origin is set."""
    repo = make_repo(base, config=config)
    write(repo, ".gitignore", (".claude/worktrees/\n" if ignore else "") + ".env\n.claude/settings.local.json\n")
    write(repo, "CLAUDE.md", "@AGENTS.md\n")
    write(repo, "AGENTS.md", "# rules\n")
    write(repo, "src/core/a.py", "x = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    if origin:
        remote = base / "origin repo.git"
        git(base, "init", "-q", "--bare", "-b", "main", str(remote))
        git(repo, "remote", "add", "origin", str(remote))
        git(repo, "push", "-q", "-u", "origin", "main")
    return repo


def commit(repo: Path, rel: str, text: str, message: str = "change") -> str:
    write(repo, rel, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").strip()


def lane_dir(repo: Path, name: str) -> Path:
    return repo / ".claude" / "worktrees" / name


def fake_gh(folder: Path, response) -> dict:
    """An environment whose PATH starts with a stand-in `gh` that prints response as JSON.

    response None: the stand-in fails, as `gh` does when not signed in.
    """
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "fake_gh.py"
    if response is None:
        script.write_text("import sys\nsys.stderr.write('not logged in')\nsys.exit(1)\n", encoding="utf-8")
    else:
        script.write_text(f"print({json.dumps(json.dumps(response))})\n", encoding="utf-8")
    if os.name == "nt":
        (folder / "gh.cmd").write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        launcher = folder / "gh"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    return {**os.environ, "PATH": str(folder) + os.pathsep + os.environ.get("PATH", "")}


def no_gh_env(base: Path) -> dict:
    """PATH with only git and Python: `gh` can't be found."""
    keep = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        folder = Path(entry)
        if any((folder / name).exists() for name in ("gh", "gh.exe", "gh.cmd")):
            continue
        keep.append(entry)
    return {**os.environ, "PATH": os.pathsep.join(keep)}
