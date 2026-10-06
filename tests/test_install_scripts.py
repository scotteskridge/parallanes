"""`install.sh` and `install.ps1`: find a real Python 3.11+ and hand over to `kit_setup.py` (plan 08).

On Windows `python` may be the Microsoft Store alias, which opens the Store instead of running
(decision 19), so the bootstrappers try each candidate and skip any that doesn't run as 3.11+.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from helpers import ROOT

pytestmark = pytest.mark.slow


def path_with(*folders):
    return os.pathsep.join([*(str(folder) for folder in folders), os.environ["PATH"]])


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs sh (Git Bash on Windows)")
def test_install_sh_skips_a_python_that_does_not_run(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    marker = tmp_path / "stub ran"
    for name in ("python3", "python"):
        stub = stubs / name
        # A Store-alias stand-in: it doesn't run Python, it exits non-zero.
        stub.write_text(f'#!/bin/sh\ntouch "{marker.as_posix()}"\nexit 9009\n', encoding="utf-8")
        stub.chmod(0o755)
    real = tmp_path / "real"
    real.mkdir()
    wrapper = real / "python3.12"
    wrapper.write_text(f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" "$@"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    target = tmp_path / "my project"

    result = subprocess.run(
        ["sh", str((ROOT / "install.sh").as_posix()), "--target", str(target), "--yes"],
        env={**os.environ, "PATH": path_with(stubs, real)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.exists()  # the stub was tried
    assert (target / ".claude" / "kit" / "python-path").read_text(encoding="utf-8").strip()
    assert (target / "AGENTS.md").is_file()


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs sh (Git Bash on Windows)")
def test_install_sh_without_any_python_says_what_to_install(tmp_path):
    empty = tmp_path / "bin"
    empty.mkdir()
    sh = shutil.which("sh")
    result = subprocess.run(
        [sh, str((ROOT / "install.sh").as_posix()), "--dry-run"],
        env={**os.environ, "PATH": str(empty)},  # install.sh uses only shell built-ins before Python
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Python 3.11" in result.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 is for Windows")
def test_install_ps1_skips_the_store_alias(tmp_path):
    store = tmp_path / "Microsoft" / "WindowsApps"
    store.mkdir(parents=True)
    marker = tmp_path / "alias ran"
    (store / "python.cmd").write_text(f'@echo off\r\ntype nul > "{marker}"\r\nexit /b 9009\r\n', encoding="utf-8")
    target = tmp_path / "my project"

    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "install.ps1"),
            "--target",
            str(target),
            "--yes",
        ],
        env={**os.environ, "PATH": path_with(store, Path(sys.executable).parent)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not marker.exists()
    recorded = (target / ".claude" / "kit" / "python-path").read_text(encoding="utf-8").strip()
    assert "WindowsApps" not in recorded
    assert (target / "AGENTS.md").is_file()
