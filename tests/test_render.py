import pytest

from kitlib.render import TemplateError, placeholders_in, render

REGISTRY = {"project_name", "test_command"}


def test_substitutes_known_placeholders():
    text = "# {{project_name}}\nRun `{{ test_command }}`."
    out = render(text, {"project_name": "Demo", "test_command": "pytest -q"}, REGISTRY)
    assert out == "# Demo\nRun `pytest -q`."


def test_unknown_placeholder_raises():
    with pytest.raises(TemplateError, match="projct_name"):
        render("{{projct_name}}", {"project_name": "Demo"}, REGISTRY)


def test_missing_value_raises():
    with pytest.raises(TemplateError, match="test_command"):
        render("{{test_command}}", {"project_name": "Demo"}, REGISTRY)


def test_escaped_braces_survive():
    out = render(r"Write \{{project_name}} in a template.", {"project_name": "Demo"}, REGISTRY)
    assert out == "Write {{project_name}} in a template."


def test_values_are_inserted_literally():
    # A value that looks like a placeholder or contains backslashes must not be re-expanded.
    out = render("{{project_name}}", {"project_name": r"{{test_command}} C:\x"}, REGISTRY)
    assert out == r"{{test_command}} C:\x"


def test_placeholders_in_lists_names_and_skips_escaped():
    assert placeholders_in(r"{{project_name}} \{{test_command}} {{ test_command }}") == {
        "project_name",
        "test_command",
    }
