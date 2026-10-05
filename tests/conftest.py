"""Make the shipped kit code importable: tests run against payload/, the code that gets installed."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
KIT_CODE = ROOT / "payload" / "kit-owned" / ".claude" / "kit"

if str(KIT_CODE) not in sys.path:
    sys.path.insert(0, str(KIT_CODE))

# git runs `git maintenance run` on its own after fetches and pushes. In throwaway test repos that
# is pure cost (twice per `lanes finish`), so every git process the tests start skips it.
# os.environ, not a fixture: the kit's subprocesses and the env dicts tests build both inherit it.
@pytest.fixture(autouse=True)
def _clear_test_control():
    """cycle_repo points the stand-in test command at its test's folder; never let it leak on."""
    yield
    os.environ.pop("KIT_TEST_CONTROL", None)


os.environ.update({
    "GIT_CONFIG_COUNT": "2",
    "GIT_CONFIG_KEY_0": "maintenance.auto", "GIT_CONFIG_VALUE_0": "false",
    "GIT_CONFIG_KEY_1": "gc.auto", "GIT_CONFIG_VALUE_1": "0",
})
