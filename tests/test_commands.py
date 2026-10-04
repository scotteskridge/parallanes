"""Command matching for the protected-commands backstop (plan 03, question 2; decision 28).

It guards against mistakes, not adversaries: the cases below are the forms an agent plausibly
writes. The documented misses are pinned too, so a change in behaviour is a visible decision.
"""
import pytest

from kitlib import commands, file_commands
from kitlib.config import DEFAULT_COMMANDS


def blocked(text, shell="bash", patterns=DEFAULT_COMMANDS):
    return [pattern for _, pattern in commands.find_protected(text, shell, patterns)]


@pytest.mark.parametrize(
    "text",
    [
        "git push --force",
        "git push origin main --force",
        "git push --force origin main",
        "git   push    --force",
        "git -C . push --force",
        "git -C 'my project' push -f",
        "git -c user.name=x push --force",
        "git --no-pager push -f",
        "git --git-dir=.git push -f",
        "git push -fu origin main",
        "git reset --hard",
        "git reset HEAD~1 --hard",
        "git clean -xdf",
        "git clean -f -d",
        "git commit --no-verify -m wip",
        "git commit -nm wip",
        "/usr/bin/git push -f",
        "cd src && git push --force",
        "npm test; git reset --hard",
        "echo hi | git push -f",
        "(cd sub && git push -f)",
        "make || git reset --hard",
        "FOO=bar git push --force",
        "env GIT_TRACE=1 git push -f",
        "sudo -u me git reset --hard",
        "timeout 30 git push --force",
        "nohup git push -f",
        "true &&\ngit push -f",
    ],
)
def test_bash_forms_are_caught(text):
    assert blocked(text), text


@pytest.mark.parametrize(
    "text",
    [
        "GIT push --force",
        "Git.exe push -f",
        "& git push --force",
        "git push origin main --force; Write-Host done",
        "C:\\Program` Files\\Git\\cmd\\git.exe reset --hard",
    ],
)
def test_powershell_forms_are_caught(text):
    assert blocked(text, shell="powershell"), text


@pytest.mark.parametrize(
    "text",
    [
        "git push",
        "git push origin main",
        "git push --force-with-lease",
        "git push --force-with-lease origin main",
        "git pushx --force",
        "git reset --soft HEAD~1",
        "git clean -n",
        "git commit -m 'use --no-verify only in emergencies'",
        "git commit -am wip",
        "git log -n 5",
        "echo 'git push --force'",
        'echo "git reset --hard"',
        "grep -- --force notes.txt",
        "legit push --force",
    ],
)
def test_safe_and_look_alike_commands_pass(text):
    assert blocked(text) == [], text


@pytest.mark.parametrize(
    "text",
    [
        "git push origin +main",  # force via refspec
        "bash -c 'git push --force'",  # inside a string
        "git pf",  # an alias
        "./scripts/force-push.sh",
    ],
)
def test_documented_misses(text):
    # Known, documented limits (decision 28). If one starts being caught, update the doc.
    assert blocked(text) == [], text


def test_the_matching_pattern_is_reported():
    assert blocked("git push origin -f") == ["git push -f"]


def test_custom_patterns_with_no_subcommand():
    assert blocked("terraform destroy -auto-approve", patterns=["terraform destroy"])
    assert blocked("rm -rf build", patterns=["rm -rf"])
    assert blocked("rm -fr build", patterns=["rm -rf"])  # clusters match in any order
    assert not blocked("rm -r build", patterns=["rm -rf"])


@pytest.mark.parametrize("bad", ["", "   ", "git push '--force"])
def test_bad_patterns_raise(bad):
    with pytest.raises(ValueError):
        commands.parse_pattern(bad)


def test_unbalanced_quotes_in_a_command_do_not_crash():
    assert blocked("git push --force 'oops") == ["git push --force"]


# ---- write targets (plan 03, question 1) --------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("Set-Content vendor/a.txt 'x'", ["vendor/a.txt"]),
        ("Set-Content -Path vendor\\a.txt -Value x", ["vendor\\a.txt"]),
        ("set-content -LiteralPath 'my dir/a.txt' -Value x", ["my dir/a.txt"]),
        ("Add-Content -Value x -Path:vendor/a.txt", ["vendor/a.txt"]),
        ("'x' | Out-File vendor/a.txt", ["vendor/a.txt"]),
        ("'x' | Out-File -FilePath vendor/a.txt -Encoding utf8", ["vendor/a.txt"]),
        ("Remove-Item vendor -Recurse -Force", ["vendor"]),
        ("rm vendor/a.txt", ["vendor/a.txt"]),
        ("del vendor/a.txt", ["vendor/a.txt"]),
        ("Move-Item src/a.txt vendor/a.txt", ["src/a.txt", "vendor/a.txt"]),
        ("Copy-Item src/a.txt -Destination vendor/", ["vendor/"]),
        ("cp src/a.txt vendor/", ["vendor/"]),
        ("New-Item -ItemType File vendor/new.txt", ["vendor/new.txt"]),
        ("ni vendor/new.txt", ["vendor/new.txt"]),
        ("Rename-Item vendor/a.txt b.txt", ["vendor/a.txt"]),
        ("Clear-Content vendor/a.txt", ["vendor/a.txt"]),
        ("Get-Date | Tee-Object -FilePath vendor/log.txt", ["vendor/log.txt"]),
        ("Set-Content -pa vendor/a.txt x", ["vendor/a.txt"]),
        ("echo x > vendor/a.txt", ["vendor/a.txt"]),
        ("echo x >>vendor/a.txt", ["vendor/a.txt"]),
        ("Get-ChildItem vendor", []),
        ("Get-Content vendor/a.txt", []),
    ],
)
def test_powershell_write_targets(text, expected):
    assert file_commands.write_targets(text, "powershell") == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("rm -rf vendor", ["vendor"]),
        ("rm -- -odd-name", ["-odd-name"]),
        ("mv vendor/a.txt src/", ["vendor/a.txt", "src/"]),
        ("cp -r src/x vendor/x", ["vendor/x"]),
        ("cp -t vendor src/a src/b", ["vendor"]),
        ("touch vendor/new", ["vendor/new"]),
        ("truncate -s 0 vendor/a", ["vendor/a"]),
        ("echo x > vendor/a.txt && cat vendor/b", ["vendor/a.txt"]),
        ("echo x 2>vendor/err.log", ["vendor/err.log"]),
        ("echo x 2>&1", []),
        ("ls vendor", []),
        ("cat vendor/a.txt", []),
    ],
)
def test_bash_write_targets(text, expected):
    assert file_commands.write_targets(text, "bash") == expected


# ---- the agent switching the checks off (question 8) --------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "KIT_ALLOW_PROTECTED=1 git commit -m x",
        "export KIT_ALLOW_PROTECTED=1",
        "$env:KIT_ALLOW_PROTECTED = '1'; git commit -m x",
        "git config core.hooksPath /dev/null",
        "git config --unset core.hooksPath",
        "git config --local core.hookspath .nohooks",
        "git -c core.hooksPath=/dev/null commit -m x",
    ],
)
def test_turning_the_checks_off_is_caught(text):
    shell = "powershell" if text.startswith("$env") else "bash"
    assert commands.disables_checks(text, shell), text


@pytest.mark.parametrize("text", ["git config --get core.hooksPath", "git config core.autocrlf false", "git commit -m x"])
def test_reading_hook_config_is_allowed(text):
    assert commands.disables_checks(text, "bash") is None


@pytest.mark.parametrize(
    "text, shell, expected",
    [
        ("rm -rf src", "bash", ["src"]),
        ("rmdir a b", "bash", ["a", "b"]),
        ("mv src/a dest/", "bash", ["src/a"]),
        ("cp -r src dest", "bash", []),
        ("touch src", "bash", []),
        ("Remove-Item src -Recurse", "powershell", ["src"]),
        ("Move-Item -Path src -Destination x", "powershell", ["src"]),
        ("Move-Item src x", "powershell", ["src"]),
        ("Copy-Item src x", "powershell", []),
    ],
)
def test_removed_targets(text, shell, expected):
    assert file_commands.removed_targets(text, shell) == expected


@pytest.mark.parametrize(
    "text, shell, expected",
    [
        ("echo x>.env", "bash", [".env"]),
        ("echo x>>vendor/a", "bash", ["vendor/a"]),
        ("cmd 2>err.log", "bash", ["err.log"]),
        ("Write-Output x>.env", "powershell", [".env"]),
        ("echo 'a>b'", "bash", []),
        ("echo x 2>&1", "bash", []),
    ],
)
def test_redirections_inside_a_word(text, shell, expected):
    assert file_commands.write_targets(text, shell) == expected


def test_git_file_commands():
    assert file_commands.removed_targets("git rm -r -- vendor src/x", "bash") == ["vendor", "src/x"]
    assert file_commands.removed_targets("git mv vendor old", "bash") == ["vendor"]
    assert file_commands.write_targets("git mv vendor old", "bash") == ["old"]
    assert file_commands.write_targets("git checkout -- a b", "bash") == ["a", "b"]
    assert file_commands.write_targets("git checkout main", "bash") == []
    assert file_commands.write_targets("git restore -s HEAD a", "powershell") == ["a"]


@pytest.mark.parametrize("text", ["grep -rn KIT_ALLOW_PROTECTED docs", "echo $KIT_ALLOW_PROTECTED"])
def test_mentioning_the_allow_variable_is_not_disabling(text):
    assert commands.disables_checks(text, "bash") is None


@pytest.mark.parametrize(
    "text, shell",
    [("set KIT_ALLOW_PROTECTED=1", "bash"), ("Set-Item env:KIT_ALLOW_PROTECTED 1", "powershell"),
     ("[Environment]::SetEnvironmentVariable('KIT_ALLOW_PROTECTED', '1')", "powershell"),
     ("env KIT_ALLOW_PROTECTED=1 git commit -m x", "bash")],
)
def test_other_ways_of_setting_the_allow_variable_are_caught(text, shell):
    assert commands.disables_checks(text, shell)


@pytest.mark.parametrize(
    "text, shell",
    [
        # Live test: quoting the variable's documented usage blocked a PR-description update.
        ('git commit -m "docs: commit with KIT_ALLOW_PROTECTED=1 when intended"', "bash"),
        ('gh pr edit 5 --body "Setting KIT_ALLOW_PROTECTED+=1 slipped past"', "bash"),
        ('grep -c "KIT_ALLOW_PROTECTED=1" docs/ai/protected-paths.md', "bash"),
        ('[[ $KIT_ALLOW_PROTECTED == 1 ]] && echo set', "bash"),
        ("Write-Host 'run with $env:KIT_ALLOW_PROTECTED = 1'", "powershell"),
        ('Select-String -Pattern "KIT_ALLOW_PROTECTED=1" -Path docs/*.md', "powershell"),
    ],
)
def test_quoting_an_assignment_is_not_setting_it(text, shell):
    assert commands.disables_checks(text, shell) is None


@pytest.mark.parametrize(
    "text, shell",
    [
        ("sudo KIT_ALLOW_PROTECTED=1 git commit -m x", "bash"),
        ("cd sub && KIT_ALLOW_PROTECTED=1 git commit -m x", "bash"),
        ("declare -x KIT_ALLOW_PROTECTED=1", "bash"),
        ("setx KIT_ALLOW_PROTECTED 1", "powershell"),
        ("$env:KIT_ALLOW_PROTECTED='1'", "powershell"),
        ("$Env:kit_allow_protected = 1", "powershell"),
        ("echo ${KIT_ALLOW_PROTECTED:=1}", "bash"),
    ],
)
def test_setting_it_in_command_position_is_still_caught(text, shell):
    assert commands.disables_checks(text, shell)
