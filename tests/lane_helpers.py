"""Throwaway projects with lanes: a main checkout (path with spaces) and a bare `origin`."""
import json
import os
import shutil
import sys
from pathlib import Path

from helpers import RULES_TOML, cache_root, git, make_repo, write

LANES_TOML = RULES_TOML + """
[[lanes]]
name = "core"
scope = "Domain logic and its tests"
owns = ["src/core/**", "tests/core/**"]
resources = { dev_port = 8001 }

[[lanes]]
name = "api"
scope = "HTTP layer"
owns = ["src/api/**"]
"""


_TEMPLATES: dict = {}  # (config, origin, ignore) -> built repo, under helpers.cache_root()


def lanes_repo(base: Path, config: str = LANES_TOML, origin: bool = True, ignore: bool = True) -> Path:
    """A committed project with lanes; origin/main exists when origin is set.

    Built once per test process for each set of arguments, then copied: building takes ~9 git
    processes (~0.8 s on Windows), copying a few milliseconds. Only the origin URL holds the folder.
    """
    key = (config, origin, ignore)
    if key not in _TEMPLATES:
        template = cache_root() / f"repo {len(_TEMPLATES)}"
        template.mkdir()
        _build_lanes_repo(template, config, origin, ignore)
        _TEMPLATES[key] = template
    template = _TEMPLATES[key]
    for child in template.iterdir():
        shutil.copytree(child, base / child.name, symlinks=True)
    repo = base / "my project"
    if origin:
        # git escapes the URL in its config file, so let git rewrite it rather than editing text.
        git(repo, "config", "remote.origin.url", str(base / "origin repo.git"))
    # The copy's index holds the template's file stat data; refresh it so plumbing that doesn't
    # (diff-files, diff-index) sees a clean tree, as in a freshly built repo.
    git(repo, "update-index", "-q", "--refresh")
    return repo


def _build_lanes_repo(base: Path, config: str, origin: bool, ignore: bool) -> Path:
    repo = make_repo(base, config=config)
    write(repo, ".gitignore", (".claude/worktrees/\n" if ignore else "") + ".env\n.claude/settings.local.json\n")
    write(repo, "CLAUDE.md", "@AGENTS.md\n")
    write(repo, "AGENTS.md", "# rules\n")
    write(repo, "src/core/a.py", "x = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    if origin:
        remote = base / "origin repo.git"
        git(base, "init", "-q", "--bare", "-b", "main", str(remote))
        # A local push runs receive-pack here with conftest's GIT_CONFIG_* entries unset (git keeps
        # a client's config from leaking into the remote), and receive-pack then starts a detached
        # `git maintenance run`. On the template that races the copy in lanes_repo (shutil.Error on
        # objects/maintenance.lock), so the origin turns it off in its own config; copies keep it.
        git(remote, "config", "receive.autogc", "false")
        git(remote, "config", "maintenance.auto", "false")
        git(repo, "remote", "add", "origin", str(remote))
        git(repo, "push", "-q", "-u", "origin", "main")
    return repo


def commit(repo: Path, rel: str, text: str, message: str = "change") -> str:
    write(repo, rel, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").strip()


def lane_dir(repo: Path, name: str) -> Path:
    return repo / ".claude" / "worktrees" / name


def fake_gh(folder: Path, response) -> dict:
    """An environment whose PATH starts with a stand-in `gh` that prints response as JSON.

    response None: the stand-in fails, as `gh` does when not signed in.
    """
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "fake_gh.py"
    if response is None:
        script.write_text("import sys\nsys.stderr.write('not logged in')\nsys.exit(1)\n", encoding="utf-8")
    else:
        script.write_text(f"print({json.dumps(json.dumps(response))})\n", encoding="utf-8")
    if os.name == "nt":
        (folder / "gh.cmd").write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        launcher = folder / "gh"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    return {**os.environ, "PATH": str(folder) + os.pathsep + os.environ.get("PATH", "")}


SCRIPTED_GH = """import json, sys
from pathlib import Path
here = Path(__file__).parent
args = sys.argv[1:]
with open(here / "gh-calls.jsonl", "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
if "--body-file" in args and args[args.index("--body-file") + 1] == "-":
    (here / "gh-stdin.txt").write_bytes(sys.stdin.buffer.read())  # as sent, like gh reads it
spec = json.loads((here / "gh-spec.json").read_text(encoding="utf-8"))
if args[:2] == ["pr", "list"]:
    state = args[args.index("--state") + 1] if "--state" in args else "open"
    prs = [pr for pr in spec["prs"] if state == "all" or pr["state"].lower() == state]
    print(json.dumps(prs))
elif args[:2] == ["pr", "create"] and spec["create"]:
    print(spec["create"])
else:
    sys.stderr.write("gh stand-in: refused " + " ".join(args))
    sys.exit(1)
"""


def scripted_gh(folder: Path, prs=(), create: str | None = "https://github.com/o/r/pull/9") -> dict:
    """An environment with a stand-in `gh` that answers `pr list` with prs (filtered by --state)
    and `pr create` with the URL create (None: it fails). Every call is logged; see gh_calls."""
    env = fake_gh(folder, [])
    (folder / "fake_gh.py").write_text(SCRIPTED_GH, encoding="utf-8")
    prs = [{"baseRefName": "main", **pr} for pr in prs]  # gh reports the base; most tests target main
    (folder / "gh-spec.json").write_text(json.dumps({"prs": prs, "create": create}), encoding="utf-8")
    return env


def gh_calls(folder: Path) -> list[list[str]]:
    log = folder / "gh-calls.jsonl"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


FAKE_TESTS = """import os, subprocess, sys
from pathlib import Path
if "KIT_TEST_CONTROL" not in os.environ:  # exit 3, never 1: a broken stand-in mustn't pass for "tests failed"
    print("stand-in test command: KIT_TEST_CONTROL is not set")
    sys.exit(3)
here = Path(os.environ["KIT_TEST_CONTROL"])  # the test's folder: flags in, run log out
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
with open(here / "test-runs.log", "a", encoding="utf-8") as log:
    log.write(head + "\\n")
race = here / "RACE"
if race.exists():  # another lane lands while these tests run (local mode retry)
    subprocess.run(["git", "update-ref", "refs/heads/main", race.read_text().strip()], check=True)
    race.unlink()
if (here / "REPORT").exists():  # test runners write reports (junit.xml): untracked, harmless
    Path("junit.xml").write_text("<testsuite/>\\n", encoding="utf-8")
if (here / "TOUCH").exists():  # a test command that edits a tracked file
    Path("src/core/a.py").write_text("x = 'changed by the tests'\\n", encoding="utf-8")
if (here / "COMMIT").exists():  # a test command that changes what would land
    Path("sneaky.txt").write_text("untested\\n", encoding="utf-8")
    subprocess.run(["git", "add", "sneaky.txt"], check=True)
    subprocess.run(["git", "commit", "-q", "-m", "made by the tests"], check=True)
print("fake tests ran")
sys.exit(1 if (here / "FAIL").exists() else 0)
"""


def cycle_repo(base: Path, mode: str = "pr") -> tuple[Path, Path]:
    """(main checkout, core lane folder) for the task cycle.

    test_command is a stand-in that logs the HEAD it ran on to <base>/test-runs.log and fails while
    <base>/FAIL exists. If <base>/RACE holds a commit, the first run moves local main there. In local mode the main checkout is detached, as decision 38 asks.
    """
    # One shared script, so the committed config (and so the cached repo) is the same for every test;
    # the script finds this test's folder through KIT_TEST_CONTROL (conftest clears it after each test).
    os.environ["KIT_TEST_CONTROL"] = str(base)
    command = f'"{Path(sys.executable).as_posix()}" "{_fake_tests_script().as_posix()}"'
    config = LANES_TOML.replace('test_command = "python -m pytest -q"', f"test_command = '{command}'\nmerge_mode = \"{mode}\"")
    repo = lanes_repo(base, config=config)
    if mode == "local":
        git(repo, "switch", "-q", "--detach", "main")
    # In-process: the lane is setup here, not what these tests are about (saves a Python start).
    from kitlib import lane_setup
    from kitlib.config import load
    lane_setup.create(repo, load(repo), ["core"])
    return repo, lane_dir(repo, "core")


def _fake_tests_script() -> Path:
    script = cache_root() / "fake tests.py"
    if not script.is_file():
        script.write_text(FAKE_TESTS, encoding="utf-8")
    return script


def recorded_test_runs(base: Path) -> list[str]:
    log = base / "test-runs.log"
    return log.read_text(encoding="utf-8").split() if log.is_file() else []


def no_gh_env(base: Path) -> dict:
    """An environment where `gh` can't tell anything: a failing stand-in shadows the real one.

    Dropping the real gh's PATH folder isn't possible: on Linux it is /usr/bin, which holds git too.
    """
    return fake_gh(Path(base).parent / "no-gh-bin", None)
