import pytest

from helpers import RULES_TOML, make_repo, write
from kitlib.config import DEFAULT_COMMANDS, DEFAULT_SECRETS, ConfigError, ConfigMissing, find_root, load


def test_root_is_found_from_a_subfolder(tmp_path):
    repo = make_repo(tmp_path)
    sub = repo / "src" / "deep"
    sub.mkdir(parents=True)
    assert find_root(sub).resolve() == repo.resolve()


def test_valid_config_loads(tmp_path):
    config = load(make_repo(tmp_path))
    assert config.project["test_command"] == "python -m pytest -q"
    (rule,) = config.rules
    assert rule.id == "no-print"
    assert rule.paths == ["src/**/*.py"]
    assert rule.exclude == ["src/cli/**"]
    assert rule.ignore_comments is True
    assert rule.regex.search("print(1)")


def test_missing_config_is_its_own_error(tmp_path):
    with pytest.raises(ConfigMissing):
        load(make_repo(tmp_path, config=None))


def config_error(tmp_path, text):
    repo = make_repo(tmp_path, config=text)
    with pytest.raises(ConfigError) as caught:
        load(repo)
    return str(caught.value)


def test_unknown_top_level_table_names_the_key(tmp_path):
    assert "chekcs" in config_error(tmp_path, RULES_TOML + "\n[chekcs]\n")


def test_unknown_rule_key_names_the_rule_and_key(tmp_path):
    text = RULES_TOML.replace('paths = ["src/**/*.py"]', 'pathes = ["src/**/*.py"]')
    message = config_error(tmp_path, text)
    assert "pathes" in message and "no-print" in message


def test_wrong_type_is_reported(tmp_path):
    message = config_error(tmp_path, RULES_TOML.replace('paths = ["src/**/*.py"]', 'paths = "src/**/*.py"'))
    assert "paths" in message and "list" in message


def test_bad_regex_is_reported(tmp_path):
    message = config_error(tmp_path, RULES_TOML.replace("'\\bprint\\('", "'print('"))
    assert "pattern" in message and "no-print" in message


def test_missing_required_key_is_reported(tmp_path):
    message = config_error(tmp_path, RULES_TOML.replace('message = "Use the logger, not print()."', ""))
    assert "message" in message


def test_duplicate_rule_ids_are_reported(tmp_path):
    rule = RULES_TOML[RULES_TOML.index("[[checks.rules]]"):]
    assert "duplicate" in config_error(tmp_path, RULES_TOML + rule).lower()


def test_invalid_toml_is_reported_with_the_file(tmp_path):
    assert "kit.toml" in config_error(tmp_path, "[project\nname = 1")


def test_lanes_and_protected_tables_load_together(tmp_path):
    text = RULES_TOML + '\n[protected]\npaths = ["vendor/**"]\n\n[[lanes]]\nname = "core"\nowns = ["src/**"]\n'
    repo = make_repo(tmp_path, config=text)
    assert [lane.name for lane in load(repo).lanes] == ["core"]


def test_invalid_glob_is_a_config_error_not_a_crash(tmp_path):
    message = config_error(tmp_path, RULES_TOML.replace('paths = ["src/**/*.py"]', 'paths = ["src/a[]b"]'))
    assert "paths" in message and "no-print" in message


@pytest.mark.parametrize(
    "old, new",
    [
        ("pattern = '\\bprint\\('", "pattern = ''"),  # would flag every line
        ('id = "no-print"', 'id = " "'),
        ('paths = ["src/**/*.py"]', 'paths = [""]'),  # would silently match nothing
    ],
)
def test_empty_strings_are_rejected(tmp_path, old, new):
    assert old in RULES_TOML
    assert "empty" in config_error(tmp_path, RULES_TOML.replace(old, new))


def test_byte_order_mark_is_accepted(tmp_path):
    # Windows PowerShell 5.1 writes UTF-8 with a BOM.
    repo = make_repo(tmp_path, config=None)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "kit.toml").write_bytes(b"\xef\xbb\xbf" + RULES_TOML.encode())
    assert load(repo).rules[0].id == "no-print"


def test_config_without_rules_is_valid(tmp_path):
    repo = make_repo(tmp_path, config='[project]\nname = "x"\n')
    assert load(repo).rules == []


# ---- [protected] (plan 03) ----------------------------------------------------------------------

def test_protected_defaults_apply_without_the_table(tmp_path):
    # A project that never wrote [protected] still gets the dangerous-command and secrets defaults.
    protected = load(make_repo(tmp_path)).protected
    assert protected.paths == []
    assert protected.commands == DEFAULT_COMMANDS
    assert protected.secrets == DEFAULT_SECRETS
    assert protected.guard_kit is True
    assert "git commit --no-verify" in DEFAULT_COMMANDS and "git commit -n" in DEFAULT_COMMANDS
    # Decision 82: every .env variant, with the committed example carved out.
    assert DEFAULT_SECRETS == [".env", ".env.*", "!.env.example"]


def test_protected_table_loads(tmp_path):
    text = RULES_TOML + '''
[protected]
paths = ["vendor/**", "docs/originals/"]
commands = ["git push --force"]
secrets = []
guard_kit = false
'''
    protected = load(make_repo(tmp_path, config=text)).protected
    assert protected.paths == ["vendor/**", "docs/originals/"]
    assert protected.commands == ["git push --force"]
    assert protected.secrets == []
    assert protected.guard_kit is False


@pytest.mark.parametrize(
    "body, expected",
    [
        ('pathes = ["x"]', "pathes"),
        ('paths = "vendor/**"', "paths"),
        ('paths = [1]', "paths"),
        ('paths = ["a[]b"]', "paths"),
        ('paths = ["../outside/**"]', "paths"),
        ('paths = ["//c/abs/**"]', "paths"),
        ('paths = ["~/home/**"]', "paths"),
        ('commands = ["  "]', "commands"),
        ("commands = [\"git push '--force\"]", "commands"),
        ('secrets = [""]', "secrets"),
        # Exemptions (decision 92): bare names only, in secrets only, after a bare name they can cancel.
        ('secrets = [".env.*", "!config/.env.example"]', "bare file name"),
        ('secrets = [".env.*", "!"]', "secrets"),
        ('secrets = ["!.env.example", ".env.*"]', "nothing before it"),
        ('secrets = ["config/*", "!.env.example"]', "nothing before it"),
        ('paths = ["vendor/**", "!vendor/keep.py"]', "only in 'secrets'"),
        ('guard_kit = "no"', "guard_kit"),
    ],
)
def test_protected_errors_name_the_key(tmp_path, body, expected):
    message = config_error(tmp_path, f"{RULES_TOML}\n[protected]\n{body}\n")
    assert "[protected]" in message and expected in message
