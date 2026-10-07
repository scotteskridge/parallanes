"""The README's quickstart runs as written (plan 12): the commands are read from the README itself,
so a change to either the README or the kit that breaks them fails here.

Plan 12's own first try found `--target ../my-project` pointing one folder too high.
"""

import re
import shutil
import subprocess

import pytest

from helpers import ROOT, git

README = ROOT / "README.md"
CLONE = "git clone https://github.com/scotteskridge/parallanes"

pytestmark = pytest.mark.skipif(shutil.which("sh") is None, reason="needs sh (Git Bash on Windows)")


def quickstart():
    text = README.read_text(encoding="utf-8")
    section = text.split("## Quickstart", 1)[1].split("\n## ", 1)[0]
    blocks = re.findall(r"```(\w+)\n(.*?)```", section, re.DOTALL)
    bash = [line.strip() for kind, body in blocks if kind == "bash" for line in body.strip().splitlines()]
    toml = [body for kind, body in blocks if kind == "toml"]
    starts = re.findall(r"`(sh \.claude/kit/parallanes lanes start [^`]+)`", section)
    return bash, toml, starts


def test_the_quickstart_has_the_steps_this_test_runs():
    bash, toml, starts = quickstart()
    assert bash[0] == CLONE
    assert len(bash) == 3 and len(toml) == 1 and len(starts) == 1


@pytest.mark.slow
def test_the_quickstart_runs_as_written(tmp_path):
    bash, toml, starts = quickstart()
    project = tmp_path / "my project parent" / "my-project"
    for folder in ("server", "public"):
        (project / folder).mkdir(parents=True)
        (project / folder / "index.js").write_text("// placeholder\n", encoding="utf-8")
    git(project, "init", "-q", "-b", "main")
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "a project")

    # Step 1: the clone is this checkout, so the test runs the kit as it is now.
    install = bash[1].replace("sh parallanes/", f'sh "{ROOT.as_posix()}/', 1).replace(".sh ", '.sh" ', 1)
    run(install + " --yes", project.parent)

    # Step 2: the README's lanes, as the owner would paste them.
    config = project / ".claude" / "kit.toml"
    config.write_text(config.read_text(encoding="utf-8") + "\n" + toml[0], encoding="utf-8")
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "install parallanes")

    # Step 3: create the lanes, then start a task in one.
    run(bash[2], project)
    run(starts[0], project / ".claude" / "worktrees" / "api")
    assert git(project / ".claude" / "worktrees" / "api", "branch", "--show-current").strip() == "api/add-book"


def run(command, cwd):
    result = subprocess.run(["sh", "-c", command], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result
