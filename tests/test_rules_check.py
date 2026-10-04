from helpers import RULES_TOML, make_repo
from kitlib.config import load
from kitlib.rules_check import check


def config_for(tmp_path, text=RULES_TOML):
    return load(make_repo(tmp_path, config=text))


def test_violation_reported_with_path_line_and_rule(tmp_path):
    findings = check(config_for(tmp_path), [("src/app.py", "x = 1\nprint(x)\n")])
    assert [(f.path, f.line, f.rule, f.check) for f in findings] == [("src/app.py", 2, "no-print", "rules")]
    assert findings[0].message == "Use the logger, not print()."


def test_every_matching_line_is_reported(tmp_path):
    findings = check(config_for(tmp_path), [("src/a.py", "print(1)\nprint(2)\n")])
    assert [f.line for f in findings] == [1, 2]


def test_files_outside_the_rule_paths_are_ignored(tmp_path):
    assert check(config_for(tmp_path), [("tools/x.py", "print(1)\n"), ("src/x.txt", "print(1)\n")]) == []


def test_excluded_files_are_ignored(tmp_path):
    assert check(config_for(tmp_path), [("src/cli/main.py", "print(1)\n")]) == []


def test_comments_are_ignored_by_default(tmp_path):
    assert check(config_for(tmp_path), [("src/a.py", "# print(1)\nx = 1  # print(2)\n")]) == []


def test_ignore_comments_false_checks_comments_too(tmp_path):
    text = RULES_TOML + "ignore_comments = false\n"
    findings = check(config_for(tmp_path, text), [("src/a.py", "# print(1)\n")])
    assert [f.line for f in findings] == [1]


def test_windows_style_paths_match(tmp_path):
    assert len(check(config_for(tmp_path), [("src\\core\\a.py", "print(1)\n")])) == 1


def test_no_rules_means_no_findings(tmp_path):
    config = config_for(tmp_path, '[project]\nname = "x"\n')
    assert check(config, [("src/a.py", "print(1)\n")]) == []
