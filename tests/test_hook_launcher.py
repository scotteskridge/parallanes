"""`.claude/kit/hook` for every hook the installer wires (plan 08).

Only the guards fail closed: `protected` and `reviewer-bash`. The others fail open by design
(decisions 9, 40, 41), so a missing Python or a crash must not turn into exit 2, which in
PreToolUse would block every edit.
"""

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
