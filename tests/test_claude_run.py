"""The live-check helper (tests/live/claude_run.py), against a stand-in `claude` that prints canned
stream-json events. The real live checks are in tests/live/ and run only with `--live`."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "live"))
from claude_run import LiveCheckError, claude_config_path, is_trusted, run_claude  # noqa: E402

STUB = """
import json, os, sys
with open(os.environ["STUB_ARGV"], "w", encoding="utf-8") as out:
    json.dump(sys.argv[1:], out)
sys.stdout.write(open(os.environ["STUB_EVENTS"], encoding="utf-8").read())
sys.exit(int(os.environ.get("STUB_EXIT", "0")))
"""

INIT = {
    "type": "system",
    "subtype": "init",
    "session_id": "s",
    "claude_code_version": "2.1.291",
    "permissionMode": "acceptEdits",
    "skills": ["next", "wrap-up"],
    "agents": ["reviewer", "Explore"],
    "plugins": [{"name": "kit", "path": "/p"}],
}
HOOK = {"type": "system", "subtype": "hook_started", "hook_name": "PreToolUse:Bash", "hook_event": "PreToolUse"}
RESULT = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "result": "done",
    "permission_denials": [{"tool_name": "Edit", "tool_input": {"file_path": "x"}}],
}


@pytest.fixture
def stub(tmp_path, monkeypatch):
    script = tmp_path / "claude_stub.py"
    script.write_text(STUB, encoding="utf-8")
    argv = tmp_path / "argv.json"
    monkeypatch.setenv("STUB_ARGV", str(argv))

    def use(*events, exit_code=0):
        path = tmp_path / "events.jsonl"
        path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
        monkeypatch.setenv("STUB_EVENTS", str(path))
        monkeypatch.setenv("STUB_EXIT", str(exit_code))
        return [sys.executable, str(script)]

    use.argv = lambda: json.loads(argv.read_text(encoding="utf-8"))
    return use


def run(stub_command, project, **options):
    return run_claude(project, "do it", permission_mode="acceptEdits", command=stub_command, **options)


def test_every_setting_that_decides_what_loads_is_passed_explicitly(stub, tmp_path):
    run(stub(INIT, RESULT), tmp_path, allowed_tools=["Read"], disallowed_tools=["Write"])
    argv = stub.argv()
    assert argv[:2] == ["-p", "do it"]
    pairs = {
        flag: argv[argv.index(flag) + 1]
        for flag in ("--output-format", "--setting-sources", "--permission-mode", "--model", "--max-budget-usd")
    }
    assert pairs == {
        "--output-format": "stream-json",
        "--setting-sources": "project,local",
        "--permission-mode": "acceptEdits",
        "--model": "haiku",
        "--max-budget-usd": "1.0",
    }
    assert "--verbose" in argv and "--include-hook-events" in argv
    assert argv[argv.index("--allowedTools") + 1] == "Read"
    assert argv[argv.index("--disallowedTools") + 1] == "Write"


def test_several_tools_turns_and_extra_flags_reach_claude(stub, tmp_path):
    run(
        stub(INIT, RESULT),
        tmp_path,
        disallowed_tools=["Bash", "PowerShell", "Write"],
        max_turns=10,
        extra_args=["--effort", "low"],
    )
    argv = stub.argv()
    at = argv.index("--disallowedTools")
    assert argv[at + 1 : at + 4] == ["Bash", "PowerShell", "Write"]
    assert argv[argv.index("--max-turns") + 1] == "10"
    assert argv[-2:] == ["--effort", "low"]


def test_claude_is_found_on_path(stub, tmp_path, monkeypatch):
    command = stub(INIT, RESULT)
    monkeypatch.setattr("shutil.which", lambda name: command[1] if name == "claude" else None)
    monkeypatch.setattr("claude_run._launcher", lambda found: [sys.executable, found])
    run_claude(tmp_path, "x", permission_mode="default")
    assert stub.argv()[:2] == ["-p", "x"]


@pytest.mark.parametrize("shim", ["claude.cmd", "CLAUDE.BAT"])
def test_a_cmd_shim_is_refused(tmp_path, monkeypatch, shim):
    # Review round 1: cmd.exe would cut a prompt at a newline or mangle `%` and `"`.
    monkeypatch.setattr("shutil.which", lambda name: str(tmp_path / shim))
    with pytest.raises(LiveCheckError, match="native"):
        run_claude(tmp_path, "x", permission_mode="default")


def test_returns_the_init_event_the_result_and_the_denials(stub, tmp_path):
    result = run(stub(INIT, HOOK, RESULT), tmp_path)
    assert result.init["claude_code_version"] == "2.1.291"
    assert result.result["result"] == "done"
    assert result.denied_paths() == ["x"]
    assert result.hooks_fired() == ["PreToolUse:Bash"]


def test_what_the_check_relies_on_must_have_loaded(stub, tmp_path):
    command = stub(INIT, HOOK, RESULT)
    run(
        command,
        tmp_path,
        expect_skills=["next"],
        expect_agents=["reviewer"],
        expect_plugins=["kit"],
        expect_hooks=["PreToolUse:Bash"],
    )
    with pytest.raises(LiveCheckError) as error:
        run(
            command,
            tmp_path,
            expect_skills=["next", "design"],
            expect_agents=["auditor"],
            expect_plugins=["kit", "other"],
            expect_hooks=["SessionStart", "PreToolUse:Edit"],
        )
    message = str(error.value)
    # Only what's missing is named.
    assert "skills not loaded: design\n" in message
    assert "agents not loaded: auditor\n" in message
    assert "plugins not loaded: other\n" in message
    assert "hooks that didn't fire: SessionStart, PreToolUse:Edit\n" in message
    assert "--bare" in message  # says the likely cause


def test_a_hook_must_be_named_as_the_stream_names_it(stub, tmp_path):
    # Review round 1: a bare event name matched any hook on that event, proving too little.
    with pytest.raises(LiveCheckError, match="PreToolUse\n"):
        run(stub(INIT, HOOK, RESULT), tmp_path, expect_hooks=["PreToolUse"])


def test_a_run_without_an_init_event_fails(stub, tmp_path):
    with pytest.raises(LiveCheckError, match="system/init"):
        run(stub(RESULT), tmp_path)


def test_a_failed_run_fails_loudly(stub, tmp_path):
    with pytest.raises(LiveCheckError, match="exit 1"):
        run(stub(INIT, RESULT, exit_code=1), tmp_path)


@pytest.mark.parametrize(
    "ending",
    [
        [],  # the stream stopped after init
        [{"type": "result", "subtype": "error_max_budget_usd", "is_error": True}],
        [{"type": "result", "subtype": "error_max_turns", "is_error": False}],
        [{"type": "result", "subtype": "success", "is_error": True, "result": "API error"}],
    ],
)
def test_a_run_that_didnt_finish_its_work_fails(stub, tmp_path, ending):
    # Review round 1: a check with only "nothing changed" assertions would pass on such a run.
    with pytest.raises(LiveCheckError, match="didn't finish"):
        run(stub(INIT, *ending), tmp_path)


def test_a_check_can_expect_an_error_result(stub, tmp_path):
    ending = {"type": "result", "subtype": "error_max_turns", "is_error": True}
    assert run(stub(INIT, ending), tmp_path, expect_error=True).result["subtype"] == "error_max_turns"


def test_a_missing_claude_fails_with_what_to_install(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(LiveCheckError, match="claude"):
        run_claude(tmp_path, "x", permission_mode="default")


def write_config(path, projects):
    path.write_text(json.dumps({"projects": projects}), encoding="utf-8")
    return path


def test_trust_is_read_from_the_claude_config(tmp_path):
    folder = tmp_path / "live check"
    folder.mkdir()
    key = folder.resolve().as_posix()
    config = write_config(tmp_path / "claude.json", {key: {"hasTrustDialogAccepted": True}})
    assert is_trusted(folder, config)
    # Review round 1: not shown that Claude Code passes trust down to subfolders, so it must be exact.
    assert not is_trusted(folder / "sub", config)
    assert not is_trusted(tmp_path / "other", config)
    assert not is_trusted(folder, write_config(tmp_path / "c2.json", {key: {"hasTrustDialogAccepted": False}}))
    assert not is_trusted(folder, tmp_path / "missing.json")


def test_an_unreadable_claude_config_says_so(tmp_path):
    broken = tmp_path / "claude.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(LiveCheckError, match="claude.json"):
        is_trusted(tmp_path, broken)


def test_the_claude_config_follows_claude_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    assert claude_config_path() == tmp_path / ".claude.json"
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    assert claude_config_path() == Path.home() / ".claude.json"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows drive letters and separators")
def test_trust_matches_windows_paths_in_any_case(tmp_path):
    folder = tmp_path / "Live Check"
    folder.mkdir()
    key = folder.resolve().as_posix().lower()
    assert is_trusted(folder, write_config(tmp_path / "c.json", {key: {"hasTrustDialogAccepted": True}}))


def test_a_check_that_needs_trust_stops_before_running(stub, tmp_path):
    config = write_config(tmp_path / "claude.json", {})
    with pytest.raises(LiveCheckError, match="trust") as error:
        run(stub(INIT, RESULT), tmp_path, needs_trust=True, claude_config=config)
    assert str(tmp_path) in str(error.value)  # names the folder to open once
    assert not (tmp_path / "argv.json").exists()


@pytest.mark.slow
@pytest.mark.parametrize("markers", [[], ["-m", "not slow"], ["-m", "live"], ["-m", "not (slow and live)"]])
def test_live_checks_are_skipped_unless_asked_for(markers):
    # Review round 1: `-m` expressions that mention live must not start one either; only --live does.
    # They cost money and need a login: the fast set, the full suite and CI must never start one.
    import subprocess

    root = Path(__file__).resolve().parent.parent
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:xdist",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=-ra --strict-markers",
            *markers,
            "tests/live",
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stdout
    assert " passed" not in done.stdout and "skipped" in done.stdout, done.stdout
