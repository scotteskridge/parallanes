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
    recorded = (target / ".claude" / "kit" / "python-path").read_text(encoding="utf-8").strip()
    assert same_file(recorded, sys.executable)
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


def same_file(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def windows_path(*folders):
    """Only these folders, git's, sh's and System32: no C:\\Windows\\py.exe to find first."""
    keep = [*folders, Path(shutil.which("git")).parent, Path(os.environ["SystemRoot"]) / "System32"]
    if shutil.which("sh"):
        keep.append(Path(shutil.which("sh")).parent)
    return os.pathsep.join(str(folder) for folder in keep)


def install_ps1(target, path, *extra):
    script = str(ROOT / "install.ps1")
    return subprocess.run(
        [shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script]
        + ["--target", str(target), "--yes", *extra],
        env={**os.environ, "PATH": path},
        capture_output=True,
        text=True,
    )


def cmd_file(path, *lines):
    path.write_bytes(("\r\n".join(["@echo off", *lines]) + "\r\n").encode("utf-8"))


windows_only = pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 is for Windows")


@windows_only
def test_install_ps1_skips_a_python_that_does_not_run(tmp_path):
    """The Store alias stand-in exits 9009; the probe moves on to the real interpreter."""
    store = tmp_path / "WindowsApps"
    store.mkdir()
    marker = tmp_path / "alias ran"
    cmd_file(store / "python.cmd", f'type nul > "{marker}"', "exit /b 9009")
    real = tmp_path / "real"
    real.mkdir()
    cmd_file(real / "python3.cmd", f'"{sys.executable}" %*')
    target = tmp_path / "my project"

    result = install_ps1(target, windows_path(store, real))

    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.exists()  # tried, and skipped because it didn't run
    recorded = (target / ".claude" / "kit" / "python-path").read_text(encoding="utf-8").strip()
    assert same_file(recorded, sys.executable)


@windows_only
def test_install_ps1_accepts_a_working_python_under_windowsapps(tmp_path):
    """python.org's install manager and Store Python put real, working pythons there (review round 1)."""
    store = tmp_path / "Microsoft" / "WindowsApps"
    store.mkdir(parents=True)
    cmd_file(store / "python.cmd", f'"{sys.executable}" %*')
    target = tmp_path / "my project"
    result = install_ps1(target, windows_path(store))
    assert result.returncode == 0, result.stdout + result.stderr
    assert same_file((target / ".claude/kit/python-path").read_text(encoding="utf-8").strip(), sys.executable)


@windows_only
def test_install_ps1_takes_a_target_with_a_trailing_backslash(tmp_path):
    """Tab completion adds one; PowerShell 5.1 then passes `"D:\\my proj\\"`, which Python reads as
    `D:\\my proj"` (review round 1)."""
    target = tmp_path / "my project"
    target.mkdir()
    result = install_ps1(str(target) + "\\", windows_path(Path(sys.executable).parent))
    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "AGENTS.md").is_file()
