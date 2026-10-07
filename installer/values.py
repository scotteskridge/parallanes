"""What the installer asks (decision 101): five values, each with a detected default.

Anything a template needs that the owner can't be expected to know (the kit's version, today's
date, how to run the kit) is filled in here, not asked. Answers from an earlier install, kept in
the manifest, win over detection, so a re-run renders the same files.
"""

import datetime
import json
import subprocess
from pathlib import Path

KIT_COMMAND = "sh .claude/kit/worklanes"  # decisions 99, 108

QUESTIONS = [
    ("project_name", "Project name"),
    ("project_description", "One-line description"),
    ("stack", "Stack (languages, frameworks, versions)"),
    ("test_command", "Command that runs the tests"),
    ("integration_branch", "Branch where finished work lands"),
]

TODO_DESCRIPTION = "TODO: one or two sentences on what this project is and who it's for."
TODO_STACK = "TODO: languages, frameworks and versions the agent must respect."

# The first marker file found decides; order is most specific first.
_STACKS = [
    ("pyproject.toml", "Python", "python -m pytest"),
    ("setup.py", "Python", "python -m pytest"),
    ("package.json", "Node.js", None),  # the test script decides
    ("go.mod", "Go", "go test ./..."),
    ("Cargo.toml", "Rust", "cargo test"),
]


def detect(target: Path, previous: dict) -> dict:
    """Defaults for every value the templates use."""
    stack, test = "", ""
    for marker, name, command in _STACKS:
        path = target / marker
        if path.is_file():
            stack = name
            test = _npm_test(path) if command is None else command
            break
    found = {
        "project_name": target.name,
        "project_description": TODO_DESCRIPTION,
        "stack": stack or TODO_STACK,
        "test_command": test,
        "integration_branch": _branch(target),
        "kit_command": KIT_COMMAND,
        "install_date": datetime.date.today().isoformat(),
    }
    # kit_command isn't an answer but how to run the kit being installed: an earlier install's
    # value would name a launcher this version doesn't ship (decision 108's rename).
    kept = {key: value for key, value in previous.items() if key in found and key != "kit_command"}
    return {**found, **kept}


def _npm_test(package: Path) -> str:
    try:
        scripts = json.loads(package.read_text(encoding="utf-8-sig")).get("scripts", {})
    except (ValueError, OSError, AttributeError):
        return ""
    return "npm test" if isinstance(scripts, dict) and scripts.get("test") else ""


def _branch(target: Path) -> str:
    """origin's default branch, else a local main or master, else main."""
    head = _git(target, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if head.startswith("origin/"):
        return head.removeprefix("origin/")
    for name in ("main", "master"):
        if _git(target, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"):
            return name
    return "main"


def _git(target: Path, *args: str) -> str:
    if not (target / ".git").exists():
        return ""
    try:
        result = subprocess.run(["git", *args], cwd=target, capture_output=True, text=True)
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def ask(defaults: dict, read=input) -> dict:
    """The five answers; Enter keeps the default shown in brackets."""
    answers = {}
    for key, question in QUESTIONS:
        typed = read(f"{question} [{defaults[key]}]: ").strip()
        answers[key] = typed or defaults[key]
    return answers


def confirm(question: str, default: bool, read=input) -> bool:
    typed = read(f"{question} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    return default if not typed else typed.startswith("y")


def toml_string(value: str) -> str:
    """value as a TOML basic string, quotes included (ARCHITECTURE §15: a `"` would break kit.toml)."""
    escaped = []
    for char in value:
        if char in '"\\':
            escaped.append("\\" + char)
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            escaped.append(f"\\u{ord(char):04X}")
        else:
            escaped.append(char)
    return '"' + "".join(escaped) + '"'
