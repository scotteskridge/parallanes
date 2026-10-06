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
# Not the receive-pack of a local push, which git starts without these: see lane_helpers' origin.
@pytest.fixture(autouse=True)
def _clear_test_control():
    """cycle_repo points the stand-in test command at its test's folder; never let it leak on."""
    yield
    os.environ.pop("KIT_TEST_CONTROL", None)


_count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))  # appended: keep a developer's own entries (safe.directory)
os.environ.update({
    f"GIT_CONFIG_KEY_{_count}": "maintenance.auto", f"GIT_CONFIG_VALUE_{_count}": "false",
    f"GIT_CONFIG_KEY_{_count + 1}": "gc.auto", f"GIT_CONFIG_VALUE_{_count + 1}": "0",
    "GIT_CONFIG_COUNT": str(_count + 2),
})


@pytest.fixture(scope="session", autouse=True)
def _fixture_cache(tmp_path_factory):
    """Where helpers keep their built-once repos: pytest's own temp folders remove read-only git
    objects and prune old runs, which a plain rmtree at exit didn't (one per xdist worker)."""
    import helpers
    import lane_helpers

    root = tmp_path_factory.mktemp("kit fixture cache")
    helpers.CACHE["root"] = root
    yield
    helpers.CACHE.clear()
    lane_helpers._TEMPLATES.clear()
