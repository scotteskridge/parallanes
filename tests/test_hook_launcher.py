"""`.claude/kit/hook` for every hook the installer wires (plan 08).

Only the guards fail closed: `protected` and `reviewer-bash`. The others fail open by design
(decisions 9, 40, 41), so a missing Python or a crash must not turn into exit 2, which in
PreToolUse would block every edit.
"""

import os
import shutil
import subprocess
import sys

import pytest

from helpers import ROOT

LAUNCHER = ROOT / "payload" / "kit-owned" / ".claude" / "kit" / "hook"
FAIL_CLOSED = ["protected", "reviewer-bash"]
FAIL_OPEN = ["ownership", "rules-check", "lane-router"]

pytestmark = [pytest.mark.slow, pytest.mark.skipif(shutil.which("sh") is None, reason="needs sh (Git Bash on Windows)")]


def launcher(tmp_path, python, cli=None):
    kit = tmp_path / "my project" / ".claude" / "kit"
    kit.mkdir(parents=True)
    shutil.copy(LAUNCHER, kit / "hook")
    (kit / "python-path").write_text(f"{python}\n", encoding="utf-8")
    if cli is not None:
        (kit / "cli.py").write_text(cli, encoding="utf-8")
    return kit


def run(kit, name):
    return subprocess.run(["sh", (kit / "hook").as_posix(), name], input="{}", capture_output=True, text=True)


@pytest.mark.parametrize("name", FAIL_CLOSED)
def test_guards_block_without_python(tmp_path, name):
    result = run(launcher(tmp_path, tmp_path / "no-such-python"), name)
    assert result.returncode == 2
    assert "python-path" in result.stderr


@pytest.mark.parametrize("name", FAIL_OPEN)
def test_other_hooks_never_block_without_python(tmp_path, name):
    result = run(launcher(tmp_path, tmp_path / "no-such-python"), name)
    assert result.returncode == 1
    assert "python-path" in result.stderr


@pytest.mark.parametrize("name", FAIL_OPEN)
def test_other_hooks_pass_a_crash_through_as_a_non_blocking_error(tmp_path, name):
    result = run(launcher(tmp_path, sys.executable, cli="raise SystemExit(3)\n"), name)
    assert result.returncode == 3


@pytest.mark.parametrize("name", FAIL_OPEN)
def test_other_hooks_keep_their_own_answers(tmp_path, name):
    result = run(launcher(tmp_path, sys.executable, cli="raise SystemExit(2)\n"), name)
    assert result.returncode == 2  # an answer the hook gave on purpose (e.g. a block it decided)


@pytest.mark.parametrize("name", FAIL_OPEN + FAIL_CLOSED)
def test_a_missing_cli_never_turns_into_a_fail_open_block(tmp_path, name):
    """Python itself exits 2 when it can't open the script: for the fail-open hooks that would be a
    block in PreToolUse (review round 1)."""
    kit = launcher(tmp_path, sys.executable)  # no cli.py
    result = run(kit, name)
    assert result.returncode == (2 if name in FAIL_CLOSED else 1)
    assert "cli.py" in result.stderr


# ---- no forks (plan 15, decision 120) --------------------------------------------------------------
# Each command the launcher starts costs ~40 ms on Windows, on every tool call. It finds its folder
# and reads python-path with the shell's own builtins, so it runs with nothing at all on PATH.

ECHO_CLI = "import sys\nprint(sys.argv[1:])\nraise SystemExit(0)\n"


def test_launcher_runs_with_no_commands_on_path(tmp_path):
    kit = launcher(tmp_path, sys.executable, cli=ECHO_CLI)
    empty = tmp_path / "empty bin"
    empty.mkdir()
    result = subprocess.run(
        [shutil.which("sh"), (kit / "hook").as_posix(), "protected"],
        input="{}",
        capture_output=True,
        text=True,
        env={"PATH": str(empty), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")},
    )
    assert result.returncode == 0, result.stderr
    assert "['hook', 'protected']" in result.stdout


def test_python_path_written_with_windows_line_endings(tmp_path):
    kit = launcher(tmp_path, sys.executable, cli=ECHO_CLI)
    (kit / "python-path").write_bytes(f"{sys.executable}\r\n".encode())
    result = run(kit, "rules-check")
    assert result.returncode == 0, result.stderr


def test_python_path_without_a_final_newline(tmp_path):
    kit = launcher(tmp_path, sys.executable, cli=ECHO_CLI)
    (kit / "python-path").write_text(str(sys.executable), encoding="utf-8")
    assert run(kit, "rules-check").returncode == 0


def test_launcher_run_by_a_bare_name_from_its_own_folder(tmp_path):
    kit = launcher(tmp_path, sys.executable, cli=ECHO_CLI)
    result = subprocess.run(["sh", "hook", "protected"], cwd=kit, input="{}", capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "['hook', 'protected']" in result.stdout
