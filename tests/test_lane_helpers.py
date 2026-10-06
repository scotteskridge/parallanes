"""The lanes fixture itself: copies of the cached template must not be raced by git in the background."""

import os
import subprocess

from lane_helpers import commit, lanes_repo


def test_pushing_to_the_fixture_origin_starts_no_maintenance(tmp_path):
    # A local push runs receive-pack in the origin with GIT_CONFIG_COUNT unset, so conftest's
    # maintenance.auto=false doesn't reach it; a detached `git maintenance run` there held
    # objects/maintenance.lock while the next test copied the template (CI run 37480171607).
    repo = lanes_repo(tmp_path)
    commit(repo, "src/core/b.py", "y = 2\n")
    result = subprocess.run(
        ["git", "push", "-q", "origin", "main"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=dict(os.environ, GIT_TRACE="1"),
        check=True,
    )
    assert "receive-pack" in result.stderr  # the trace covers the origin's side of the push
    assert "maintenance run" not in result.stderr
