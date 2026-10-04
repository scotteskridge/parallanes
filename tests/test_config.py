import pytest

from helpers import RULES_TOML, make_repo, write
from kitlib.config import ConfigError, ConfigMissing, find_root, load


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


def test_tables_owned_by_later_plans_are_tolerated(tmp_path):
    text = RULES_TOML + '\n[protected]\npaths = ["vendor/**"]\n\n[[lanes]]\nname = "core"\n'
    repo = make_repo(tmp_path, config=text)
    assert load(repo).raw["lanes"][0]["name"] == "core"


def test_config_without_rules_is_valid(tmp_path):
    repo = make_repo(tmp_path, config='[project]\nname = "x"\n')
    assert load(repo).rules == []
