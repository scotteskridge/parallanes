"""Time each kit hook per call, as Claude Code runs it (plan 15, decision 120). Dev-only: not installed.

Installs the kit from this checkout into a throwaway project with two lanes, starts a task in lane
`core`, then runs every hook many times: through the `sh` launcher settings.json uses, and as
`python cli.py hook <name>` (the hook's own time). Prints a Markdown table of medians.

    .venv/Scripts/python tools/hook_timing.py [--runs 15] [--python PATH]

`--python` is the interpreter the hooks run with (default: this one's base Python, not a venv's
shim, which on Windows adds ~65 ms a call that an installed project needn't pay).
"""

import argparse
import json
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LANES = """
[[lanes]]
name = "core"
scope = "Domain logic"
owns = ["src/core/**"]

[[lanes]]
name = "api"
scope = "HTTP layer"
owns = ["src/api/**"]
"""


def git(folder: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=folder, check=True, capture_output=True)


def kit(folder: Path, *args: str) -> None:
    result = subprocess.run(
        ["sh", ".claude/kit/parallanes", *args], cwd=folder, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        raise SystemExit(f"parallanes {' '.join(args)} failed:\n{result.stdout}{result.stderr}")


def build(base: Path, python: str) -> Path:
    project = base / "timing project"
    project.mkdir()
    git(project, "init", "-q", "-b", "main")
    git(project, "config", "user.name", "timing")
    git(project, "config", "user.email", "timing@example.com")
    (project / "README.md").write_text("timing\n", encoding="utf-8")
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "init")
    setup = subprocess.run(
        [python, str(ROOT / "kit_setup.py"), "--target", str(project), "--yes"], capture_output=True, text=True
    )
    if setup.returncode != 0:
        raise SystemExit(f"kit_setup.py failed:\n{setup.stdout}{setup.stderr}")
    (project / ".claude" / "kit" / "python-path").write_text(python + "\n", encoding="utf-8")
    config = project / ".claude" / "kit.toml"
    text = re.sub(r"(?m)^test_command = .*$", 'test_command = "echo ok"', config.read_text(encoding="utf-8"))
    config.write_text(text + LANES, encoding="utf-8")
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "kit")
    kit(project, "lanes", "create")
    kit(project / ".claude" / "worktrees" / "core", "lanes", "start", "timing")
    return project


def payload(cwd: Path, event: str, tool: str | None, tool_input: dict) -> str:
    return json.dumps(
        {"session_id": "timing", "hook_event_name": event, "cwd": str(cwd), "tool_name": tool, "tool_input": tool_input}
    )


def cases(project: Path) -> list:
    lane = project / ".claude" / "worktrees" / "core"
    edit_lane = {"file_path": str(lane / "src" / "core" / "a.py")}
    edit_main = {"file_path": str(project / "README.md")}
    return [
        ("protected (Bash, main checkout)", "protected", project, "PreToolUse", "Bash", {"command": "git status"}),
        ("protected (Edit, lane)", "protected", lane, "PreToolUse", "Edit", edit_lane),
        ("ownership (Edit, lane)", "ownership", lane, "PreToolUse", "Edit", edit_lane),
        ("rules-check (Edit, main checkout)", "rules-check", project, "PostToolUse", "Edit", edit_main),
        ("reviewer-bash (Bash)", "reviewer-bash", project, "PreToolUse", "Bash", {"command": "git status"}),
        ("lane-router (lane, once a session)", "lane-router", lane, "SessionStart", None, {}),
    ]  # fmt: skip


def median_ms(argv: list, cwd: Path, stdin: str, runs: int) -> tuple[float, int]:
    times, code = [], 0
    for _ in range(runs):
        start = time.perf_counter()
        result = subprocess.run(argv, cwd=cwd, input=stdin, capture_output=True, text=True, encoding="utf-8")
        times.append((time.perf_counter() - start) * 1000)
        code = result.returncode
    return statistics.median(times), code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=15)
    base_python = Path(sys.base_prefix) / ("python.exe" if sys.platform == "win32" else "bin/python3")
    parser.add_argument("--python", default=str(base_python))
    args = parser.parse_args()
    if shutil.which("sh") is None:
        raise SystemExit("needs sh (Git Bash on Windows)")
    base = Path(tempfile.mkdtemp(prefix="hook timing "))
    try:
        project = build(base, args.python)
        cli = project / ".claude" / "kit" / "cli.py"
        launcher = (project / ".claude" / "kit" / "hook").as_posix()
        start_up, _ = median_ms([args.python, "-c", "pass"], project, "", args.runs)
        sh_start, _ = median_ms(["sh", "-c", ":"], project, "", args.runs)
        system = f"{platform.system()} {platform.release()}"
        version = subprocess.run([args.python, "--version"], capture_output=True, text=True).stdout.strip()
        print(f"{system}, {version}, {args.runs} runs, medians")
        print(f"`python -c pass`: {start_up:.0f} ms; `sh -c :`: {sh_start:.0f} ms\n")
        print("| Hook | Own time (python cli.py) | Via `sh` launcher | Exit |")
        print("| --- | --- | --- | --- |")
        for label, name, cwd, event, tool, tool_input in cases(project):
            stdin = payload(cwd, event, tool, tool_input)
            direct, code = median_ms([args.python, str(cli), "hook", name], cwd, stdin, args.runs)
            via_sh, _ = median_ms(["sh", launcher, name], cwd, stdin, args.runs)
            print(f"| {label} | {direct:.0f} ms | {via_sh:.0f} ms | {code} |")
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
