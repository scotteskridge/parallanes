"""The README's quickstart runs as written (plan 12): every command comes from the README's own code
blocks, in order, so a step the README leaves out fails here instead of being slipped in by the test.

Two substitutions only: the clone is this checkout (the test runs the kit as it is now), and the
installer gets `--yes` (the README says it asks questions; a test can't answer them). The project
is the one the README asks for: a git repository with a commit on `main`.

Review round 1 found the first version adding the commit the README forgot, so a reader's lanes
came out without the kit.
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
    """[(kind, body)] for each code block of the Quickstart section, in order, and the
    `lanes start` the prose tells the api lane to run."""
    text = README.read_text(encoding="utf-8")
    section = text.split("## Quickstart", 1)[1].split("\n## ", 1)[0]
    blocks = re.findall(r"```(\w+)\n(.*?)```", section, re.DOTALL)
    starts = re.findall(r"`(sh \.claude/kit/parallanes lanes start [^`]+)`", section)
    return blocks, starts


def test_the_quickstart_starts_from_the_published_repo():
    blocks, starts = quickstart()
    assert blocks[0][0] == "bash" and blocks[0][1].strip() == CLONE
    assert [kind for kind, _ in blocks].count("toml") == 1 and len(starts) == 1


@pytest.mark.slow
def test_the_quickstart_runs_as_written(tmp_path):
    blocks, starts = quickstart()
    here = tmp_path / "my projects"
    project = here / "my-project"
    project.mkdir(parents=True)
    (project / "README.md").write_text("A project.\n", encoding="utf-8")
    git(project, "init", "-q", "-b", "main")
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "a project")

    cwd = here
    for kind, body in blocks:
        if kind == "toml":
            config = cwd / ".claude" / "kit.toml"
            config.write_text(config.read_text(encoding="utf-8") + "\n" + body, encoding="utf-8")
            continue
        assert kind == "bash", kind
        for line in body.strip().splitlines():
            command = line.strip()
            if command == CLONE:
                continue
            if command.startswith("cd "):
                cwd = cwd / command.removeprefix("cd ").strip()
                continue
            if command.startswith("sh parallanes/install.sh"):
                command = command.replace("sh parallanes/", f'sh "{ROOT.as_posix()}/', 1)
                command = command.replace("install.sh", 'install.sh"', 1) + " --yes"
            run(command, cwd)

    run(starts[0], project / ".claude" / "worktrees" / "api")
    assert git(project / ".claude" / "worktrees" / "api", "branch", "--show-current").strip() == "api/add-book"


def run(command, cwd):
    result = subprocess.run(["sh", "-c", command], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result
