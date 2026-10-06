"""Hook mode: Claude Code sends PostToolUse JSON on stdin; exit 2 feeds stderr back to Claude."""

import json

from helpers import RULES_TOML, hook_payload, make_repo, run_cli, write


def hook(repo, payload):
    return run_cli(repo, "hook", "rules-check", stdin=payload)


def test_violation_exits_2_with_findings_on_stderr(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/app.py", "x = 1\nprint(x)\n")
    result = hook(repo, hook_payload(repo, "src/app.py"))
    assert result.returncode == 2
    assert "src/app.py:2: [rules/no-print] Use the logger, not print()." in result.stderr
    assert "kit.toml" in result.stderr  # tells Claude where the rule lives


def test_clean_file_exits_0_silently(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/app.py", "x = 1\n")
    result = hook(repo, hook_payload(repo, "src/app.py", tool="Write"))
    assert (result.returncode, result.stderr) == (0, "")


def test_file_no_rule_covers_exits_0(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "notes.txt", "print(1)\n")
    assert hook(repo, hook_payload(repo, "notes.txt")).returncode == 0


def test_deleted_file_exits_0(tmp_path):
    repo = make_repo(tmp_path)
    assert hook(repo, hook_payload(repo, "src/gone.py")).returncode == 0


def test_file_outside_the_project_exits_0(tmp_path):
    repo = make_repo(tmp_path)
    outside = write(tmp_path, "elsewhere.py", "print(1)\n")
    payload = json.loads(hook_payload(repo, "x"))
    payload["tool_input"]["file_path"] = str(outside)
    assert hook(repo, json.dumps(payload)).returncode == 0


def test_broken_config_fails_open_with_a_visible_error(tmp_path):
    # Decision 9: never block an edit over the kit itself; exit 1 is a non-blocking hook error.
    repo = make_repo(tmp_path, config=RULES_TOML + "\n[chekcs]\n")
    write(repo, "src/app.py", "print(1)\n")
    result = hook(repo, hook_payload(repo, "src/app.py"))
    assert result.returncode == 1
    assert "chekcs" in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_config_exits_0(tmp_path):
    # Kit not set up in this project: nothing to enforce.
    repo = make_repo(tmp_path, config=None)
    write(repo, "src/app.py", "print(1)\n")
    assert hook(repo, hook_payload(repo, "src/app.py")).returncode == 0


def test_garbage_stdin_fails_open(tmp_path):
    result = hook(make_repo(tmp_path), "not json")
    assert result.returncode == 1
    assert "Traceback" not in result.stderr


def test_payload_without_a_file_path_exits_0(tmp_path):
    repo = make_repo(tmp_path)
    payload = json.dumps({"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": "ls"}})
    assert hook(repo, payload).returncode == 0


def test_unknown_hook_name_is_a_non_blocking_error(tmp_path):
    # A typo in settings.json must not send usage text to Claude (exit 2) after every edit.
    repo = make_repo(tmp_path)
    result = run_cli(repo, "hook", "rules-chek", stdin=hook_payload(repo, "src/a.py"))
    assert result.returncode == 1


def test_notebook_edits_use_notebook_path(tmp_path):
    text = RULES_TOML.replace('paths = ["src/**/*.py"]', 'paths = ["**/*.ipynb"]')
    repo = make_repo(tmp_path, config=text)
    write(repo, "nb/a.ipynb", '{"source": "print(1)"}\n')
    payload = json.dumps(
        {
            "cwd": str(repo),
            "tool_name": "NotebookEdit",
            "tool_input": {"notebook_path": str(repo / "nb" / "a.ipynb")},
        }
    )
    assert hook(repo, payload).returncode == 2
