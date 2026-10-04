from helpers import RULES_TOML, git, make_repo, run_cli, write


def test_explicit_files_with_a_violation_exit_1_and_list_it(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/app.py", "x = 1\nprint(x)\n")
    result = run_cli(repo, "check", "rules", "src/app.py")
    assert result.returncode == 1
    assert "src/app.py:2: [rules/no-print] Use the logger, not print()." in result.stdout


def test_clean_files_exit_0(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/app.py", "x = 1\n")
    result = run_cli(repo, "check", "rules", "src/app.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_arguments_checks_every_tracked_file(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "print(1)\n")
    write(repo, "src/untracked.py", "print(2)\n")
    git(repo, "add", "src/a.py", ".claude/kit.toml")
    result = run_cli(repo, "check", "all")
    assert result.returncode == 1
    assert "src/a.py:1" in result.stdout
    assert "untracked" not in result.stdout


def test_runs_from_a_subfolder_with_paths_relative_to_it(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/app.py", "print(1)\n")
    result = run_cli(repo / "src", "check", "rules", "app.py")
    assert result.returncode == 1
    assert "src/app.py:1" in result.stdout


def test_config_error_exits_2_with_the_reason(tmp_path):
    repo = make_repo(tmp_path, config=RULES_TOML + "\n[chekcs]\n")
    write(repo, "src/app.py", "x = 1\n")
    result = run_cli(repo, "check", "rules", "src/app.py")
    assert result.returncode == 2
    assert "chekcs" in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_config_exits_2(tmp_path):
    repo = make_repo(tmp_path, config=None)
    result = run_cli(repo, "check", "all")
    assert result.returncode == 2
    assert "kit.toml" in result.stderr


def test_file_outside_the_project_is_a_usage_error(tmp_path):
    repo = make_repo(tmp_path)
    outside = write(tmp_path, "elsewhere.py", "print(1)\n")
    result = run_cli(repo, "check", "rules", str(outside))
    assert result.returncode == 2
    assert "outside the project" in result.stderr


def test_missing_or_folder_argument_is_an_error_not_clean(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "src").mkdir()
    for name in ("src/mian.py", "src"):
        result = run_cli(repo, "check", "rules", name)
        assert result.returncode == 2, name
        assert "not a file" in result.stderr


def test_non_ascii_findings_print_without_crashing(tmp_path):
    # On Windows a pipe or cp1252 console used to raise UnicodeEncodeError here.
    repo = make_repo(tmp_path, config=RULES_TOML.replace("Use the logger, not print().", "Use log → not print"))
    write(repo, "src/données.py", "print(1)\n")
    result = run_cli(repo, "check", "rules", "src/données.py")
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "→" in result.stdout and "données" in result.stdout


def test_staged_submodule_is_skipped(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "x = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "start")
    # A gitlink to a commit that only exists in the submodule's own repository (as in real life),
    # at a path a rule covers: reading it with `git show` would fail.
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{'1' * 40},src/sub.py")
    result = run_cli(repo, "check", "all", "--staged")
    assert result.returncode == 0, result.stderr


def test_staged_rename_checks_the_new_name(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/old name.py", "print(1)\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "start")
    git(repo, "mv", "src/old name.py", "src/new name.py")
    result = run_cli(repo, "check", "all", "--staged")
    assert result.returncode == 1
    assert "src/new name.py:1" in result.stdout


def test_staged_reads_index_not_worktree(tmp_path):
    repo = make_repo(tmp_path)
    # Violation staged, then "fixed" only in the working tree: the commit would still contain it.
    write(repo, "src/a.py", "print(1)\n")
    git(repo, "add", "src/a.py")
    write(repo, "src/a.py", "x = 1\n")
    # And the reverse: clean in the index, violation only in the working tree.
    write(repo, "src/b.py", "x = 1\n")
    git(repo, "add", "src/b.py")
    write(repo, "src/b.py", "print(2)\n")
    result = run_cli(repo, "check", "all", "--staged")
    assert result.returncode == 1
    assert "src/a.py:1" in result.stdout
    assert "src/b.py" not in result.stdout


def test_staged_ignores_deleted_files(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "x = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "start")
    git(repo, "rm", "-q", "src/a.py")
    assert run_cli(repo, "check", "all", "--staged").returncode == 0


def test_diff_checks_only_files_changed_since_base(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/old.py", "print('already here')\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "switch", "-q", "-c", "feature")
    write(repo, "src/new.py", "print('new')\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feature")
    result = run_cli(repo, "check", "all", "--diff", "main")
    assert result.returncode == 1
    assert "src/new.py:1" in result.stdout
    assert "src/old.py" not in result.stdout


def test_binary_files_are_skipped(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "blob.py").write_bytes(b"print(\x00\x01")
    assert run_cli(repo, "check", "rules", "src/blob.py").returncode == 0


def test_help_lists_the_commands(tmp_path):
    result = run_cli(tmp_path, "--help")
    assert result.returncode == 0
    for command in ("check", "hook", "changelog"):
        assert command in result.stdout
