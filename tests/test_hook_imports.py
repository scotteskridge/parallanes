"""What each hook loads per call (plan 15, decision 120).

The hooks run on every tool call, so whatever they import is paid every time: `argparse` and the CLI
commands' modules cost ~60 ms on Windows, `subprocess` ~15 ms. Two checks: the modules each hook
loads in a fresh Python (exact, never flaky), and a time limit on the hook path's imports (catches a
slow import nobody listed).
"""

import json
import subprocess
import sys

import pytest

from helpers import CLI, make_repo, run_cli
from lane_helpers import lane_dir, lanes_repo

# The CLI commands' modules: no hook uses them.
CLI_ONLY = {
    "argparse",
    "kitlib.changelog",
    "kitlib.settings",
    "kitlib.render",
    "kitlib.lane_cli",
    "kitlib.lane_setup",
    "kitlib.lane_cycle",
    "kitlib.lane_status",
    "kitlib.lane_pr",
    "kitlib.lane_merged",
    "kitlib.next_facts",
}
LANE_CODE = {"kitlib.lane_hooks", "kitlib.lanes", "kitlib.lane_boundary", "kitlib.session_lock", "kitlib.lane_deps"}
# Only the session-start briefing needs these.
ROUTER_ONLY = {"kitlib.session_lock", "kitlib.lane_deps"}

DRIVER = """
import io, json, sys
kit, name, out = sys.argv[1:4]
sys.path.insert(0, kit)
sys.stdin = io.StringIO(sys.stdin.read())
import cli
code = cli.main(["hook", name])
with open(out, "w", encoding="utf-8") as handle:
    json.dump({"code": code, "modules": sorted(sys.modules)}, handle)
"""


def loaded(tmp_path, cwd, name, event, tool_input, tool="Edit"):
    payload = {"hook_event_name": event, "cwd": str(cwd), "tool_name": tool, "tool_input": tool_input}
    out = tmp_path / "modules.json"
    result = subprocess.run(
        [sys.executable, "-c", DRIVER, str(CLI.parent), name, str(out)],
        cwd=cwd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0 and out.exists(), result
    report = json.loads(out.read_text(encoding="utf-8"))
    return report["code"], set(report["modules"])


def unwanted(modules: set, forbidden: set) -> list:
    return sorted(modules & forbidden)


def test_protected_loads_neither_the_cli_nor_the_lane_code_nor_subprocess(tmp_path):
    repo = make_repo(tmp_path)
    for tool, tool_input in (("Bash", {"command": "git status"}), ("Edit", {"file_path": str(repo / "a.py")})):
        code, modules = loaded(tmp_path, repo, "protected", "PreToolUse", tool_input, tool)
        assert code == 0
        assert unwanted(modules, CLI_ONLY | LANE_CODE | {"subprocess", "kitlib.rules_check"}) == []


def test_rules_check_loads_no_lane_code_nor_subprocess(tmp_path):
    repo = make_repo(tmp_path)
    code, modules = loaded(tmp_path, repo, "rules-check", "PostToolUse", {"file_path": str(repo / "a.py")})
    assert code == 0
    assert unwanted(modules, CLI_ONLY | LANE_CODE | {"subprocess"}) == []


def test_reviewer_guard_loads_no_cli_or_lane_code(tmp_path):
    repo = make_repo(tmp_path)
    code, modules = loaded(tmp_path, repo, "reviewer-bash", "PreToolUse", {"command": "git status"}, "Bash")
    assert code == 0
    assert unwanted(modules, CLI_ONLY | LANE_CODE | {"subprocess"}) == []


@pytest.mark.slow
def test_ownership_in_a_lane_starts_no_process_and_skips_the_briefing_code(tmp_path):
    repo = lanes_repo(tmp_path, origin=False)
    assert run_cli(repo, "lanes", "create").returncode == 0
    lane = lane_dir(repo, "core")
    for target in ("src/core/x.py", "src/api/x.py"):  # allowed, then asked
        code, modules = loaded(tmp_path, lane, "ownership", "PreToolUse", {"file_path": str(lane / target)})
        assert code == 0
        assert unwanted(modules, CLI_ONLY | ROUTER_ONLY | {"subprocess", "kitlib.rules_check"}) == []


@pytest.mark.slow
def test_lane_router_loads_no_cli_code(tmp_path):
    repo = lanes_repo(tmp_path, origin=False)
    assert run_cli(repo, "lanes", "create").returncode == 0
    code, modules = loaded(tmp_path, lane_dir(repo, "core"), "lane-router", "SessionStart", {})
    assert code == 0
    assert unwanted(modules, CLI_ONLY) == []


# The kit's own imports on the hook path, as a multiple of the standard modules every hook needs
# (json, pathlib, re, tomllib) timed first in the same process: a ratio, so a slow CI runner can't
# fail it. Measured (Windows, Python 3.12, `-I -S`): 0.38 after plan 15, 1.35 before it (argparse, the
# command modules, dataclasses, subprocess). The limit is about twice the measured ratio.
IMPORT_RATIO_LIMIT = 0.8

IMPORT_TIMER = """
import sys, time
sys.path.insert(0, sys.argv[1])
start = time.perf_counter()
import json, pathlib, re, tomllib
baseline = time.perf_counter() - start
start = time.perf_counter()
import cli
from kitlib import hooks, lane_hooks, protected, rules_check
print((time.perf_counter() - start) / baseline)
"""


def test_hook_path_imports_stay_under_the_limit():
    """Best of five fresh processes: noise only ever makes a run slower. `-S`: site (an editable
    install's path hook) would load some of the standard modules before the timer starts."""
    ratios = []
    for _ in range(5):
        argv = [sys.executable, "-I", "-S", "-c", IMPORT_TIMER, str(CLI.parent)]
        result = subprocess.run(argv, capture_output=True, text=True, check=True)
        ratios.append(float(result.stdout))
    assert min(ratios) < IMPORT_RATIO_LIMIT, (
        f"the hook path's imports took {min(ratios):.2f}x the standard modules' (limit {IMPORT_RATIO_LIMIT}x)"
    )
