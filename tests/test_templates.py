"""Every project-owned template must render cleanly, stay in budget and link correctly."""

import posixpath
import re
import tomllib
from pathlib import Path

import pytest

from kitlib.render import placeholders_in, render

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "payload" / "templates"
REGISTRY_FILE = ROOT / "payload" / "placeholders.toml"
SUFFIX = ".tmpl"  # every template carries it; the installer strips it


def registry() -> dict:
    return tomllib.loads(REGISTRY_FILE.read_text(encoding="utf-8"))


def template_files() -> list[Path]:
    return sorted(p for p in TEMPLATES.rglob("*") if p.is_file())


def installed_name(path: Path) -> str:
    """Path the template will have in a project, relative to the project root."""
    rel = path.relative_to(TEMPLATES).as_posix()
    return rel[: -len(SUFFIX)] if rel.endswith(SUFFIX) else rel


def read(installed: str) -> str:
    return (TEMPLATES / (installed + SUFFIX)).read_text(encoding="utf-8")


def test_templates_exist():
    assert len(template_files()) > 10


def test_every_template_carries_the_suffix():
    # The suffix stops this repo's own tools treating templates as live files: a CLAUDE.md or
    # .gitignore in payload/ would otherwise be loaded by Claude Code or applied by git here.
    # .gitkeep files only hold empty folders open and are copied as they are.
    for path in template_files():
        assert path.name == ".gitkeep" or path.name.endswith(SUFFIX), f"{path} lacks {SUFFIX}"


def test_every_placeholder_is_registered():
    known = set(registry())
    for path in template_files():
        unknown = placeholders_in(path.read_text(encoding="utf-8")) - known
        assert not unknown, f"{installed_name(path)} uses unregistered {sorted(unknown)}"


def test_every_registry_entry_is_described_and_has_an_example():
    for name, entry in registry().items():
        assert entry.get("description"), f"{name} has no description"
        assert entry.get("example"), f"{name} has no example"


def test_every_template_renders_with_sample_values():
    entries = registry()
    values = {name: entry["example"] for name, entry in entries.items()}
    for path in template_files():
        source = path.read_text(encoding="utf-8")
        out = render(source, values, set(entries))
        # The only braces allowed in the output are ones the template escaped on purpose.
        escaped = source.count("\\{{")
        assert out.count("{{") == escaped, f"{installed_name(path)} left braces behind"


@pytest.mark.parametrize(
    "installed, limit",
    [("AGENTS.md", 80), ("CLAUDE.md", 40)],
)
def test_instruction_budgets(installed, limit):
    lines = read(installed).count("\n")
    assert lines <= limit, f"{installed} is {lines} lines; budget {limit}"


def test_rules_files_stay_under_200_lines():
    for path in (TEMPLATES / ".claude" / "rules").glob("*" + SUFFIX):
        assert path.read_text(encoding="utf-8").count("\n") <= 200, path.name


def test_claude_md_imports_agents_md():
    assert read("CLAUDE.md").splitlines()[0].strip() == "@AGENTS.md"


def test_rules_files_have_paths_frontmatter():
    # Claude Code loads every .md in .claude/rules/; without `paths:` a file loads in every session.
    rules = list((TEMPLATES / ".claude" / "rules").glob("*" + SUFFIX))
    assert rules
    for path in rules:
        text = path.read_text(encoding="utf-8")
        match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
        assert match, f"{path.name} has no frontmatter"
        # An empty `paths:` loads in every session, so at least one glob must follow it.
        assert re.search(r"^paths:\s*\n(\s+- \S.*\n?)+", match.group(1) + "\n", re.MULTILINE), (
            f"{path.name} has no paths: globs"
        )


def test_relative_links_resolve():
    installed = {installed_name(p) for p in template_files()}
    for path in template_files():
        if not path.name.endswith(".md" + SUFFIX):
            continue
        here = posixpath.dirname(installed_name(path))
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", path.read_text(encoding="utf-8")):
            if re.match(r"[a-z]+:", target):
                continue  # external URL
            resolved = posixpath.normpath(posixpath.join(here, target))
            is_dir = any(name.startswith(resolved + "/") for name in installed)
            assert resolved in installed or is_dir, f"{installed_name(path)} links to missing {target}"


def test_templates_are_lf():
    for path in template_files():
        assert b"\r\n" not in path.read_bytes(), f"{installed_name(path)} has CRLF line endings"


def test_rendered_kit_toml_is_a_valid_config(tmp_path):
    # The installed config must load cleanly, or every check and hook would fail on day one.
    from kitlib.config import load

    entries = registry()
    values = {name: entry["example"] for name, entry in entries.items()}
    rendered = render(read(".claude/kit.toml"), values, set(entries))
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "kit.toml").write_text(rendered, encoding="utf-8")
    config = load(tmp_path)
    assert config.project["test_command"] == values["test_command"]
    assert config.rules == []


def test_rendered_kit_toml_protects_with_the_documented_defaults(tmp_path):
    # The template spells the defaults out; they must equal the code's, and generate valid rules.
    from kitlib.config import DEFAULT_COMMANDS, DEFAULT_SECRETS, load
    from kitlib.protected import path_reason
    from kitlib.settings import expected_rules

    entries = registry()
    values = {name: entry["example"] for name, entry in entries.items()}
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "kit.toml").write_text(
        render(read(".claude/kit.toml"), values, set(entries)), encoding="utf-8"
    )
    protected = load(tmp_path).protected
    assert protected.commands == DEFAULT_COMMANDS
    assert protected.secrets == DEFAULT_SECRETS
    assert protected.guard_kit is True
    assert path_reason(protected, ".env.example") is None  # projects commit this one
    rules = expected_rules(protected)
    assert "Read(.env)" in rules["deny"] and "Bash(git push --force *)" in rules["deny"]


def examples() -> dict:
    """The TOML examples in docs/ai/kit-toml.md, by the name in the comment above each (plan 16)."""
    entries = registry()
    values = {name: entry["example"] for name, entry in entries.items()}
    text = render(read("docs/ai/kit-toml.md"), values, set(entries))
    found = dict(re.findall(r"<!-- example: ([a-z-]+) -->\n```toml\n(.*?)```", text, re.DOTALL))
    assert found, "docs/ai/kit-toml.md has no marked examples"
    return found


def _kit_toml_with(tmp_path, *names):
    """The rendered kit.toml with the named examples from docs/ai/kit-toml.md added, then loaded.
    The project-lanes example's keys go into the existing [project] table."""
    from kitlib.config import load

    entries = registry()
    values = {name: entry["example"] for name, entry in entries.items()}
    text = render(read(".claude/kit.toml"), values, set(entries))
    found = examples()
    for name in names:
        block = found[name]
        if name == "project-lanes":
            text = text.replace("[project]\n", block, 1)
        else:
            text += "\n" + block
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "kit.toml").write_text(text, encoding="utf-8")
    return load(tmp_path)


def test_every_kit_toml_example_is_documented_and_loads(tmp_path):
    # The examples are what owners copy; together they must make a valid config.
    assert set(examples()) == {"project-lanes", "rules", "hooks", "shared-defaults", "shared-repo-wide", "lanes"}
    config = _kit_toml_with(tmp_path, *examples())
    assert [rule.id for rule in config.rules] == ["no-print"]
    assert config.hooks.switched_off == frozenset()


def test_kit_toml_lane_example_loads_with_the_documented_defaults(tmp_path):
    from kitlib.config import LaneSettings

    config = _kit_toml_with(tmp_path, "project-lanes", "lanes")
    assert [lane.name for lane in config.lanes] == ["core", "api"]
    defaults = LaneSettings()
    settings = config.lane_settings
    # The values shown are documented as the defaults: they must be.
    assert (settings.merge_mode, settings.worktree_root, settings.ownership, settings.shared_paths) == (
        defaults.merge_mode,
        defaults.worktree_root,
        defaults.ownership,
        defaults.shared_paths,
    )


REPO_WIDE_EXAMPLE = ("/.gitignore", "/package.json")


def test_kit_toml_shared_defaults_are_the_real_defaults(tmp_path):
    from kitlib.config import LaneSettings

    assert _kit_toml_with(tmp_path, "shared-defaults", "lanes").lane_settings.shared == LaneSettings().shared


def test_kit_toml_repo_wide_example_loads_with_its_steward(tmp_path):
    from kitlib.config import LaneSettings
    from kitlib.shared_zones import Zone

    shared = _kit_toml_with(tmp_path, "shared-defaults", "shared-repo-wide", "lanes").lane_settings.shared
    assert shared == (*LaneSettings().shared, Zone(REPO_WIDE_EXAMPLE, "ask", "core"))


def test_kit_toml_repo_wide_example_alone_keeps_the_defaults(tmp_path):
    # Plan 13's review round 1: using only this example dropped every default shared path.
    from kitlib.config import LaneSettings
    from kitlib.shared_zones import Zone

    shared = _kit_toml_with(tmp_path, "shared-repo-wide", "lanes").lane_settings.shared
    assert shared == (Zone(REPO_WIDE_EXAMPLE, "ask", "core"), *LaneSettings().shared)


def test_installed_kit_toml_stays_short():
    # Plan 16: the reference moved to docs/ai/kit-toml.md; the file a new user opens stays a page.
    words = len(read(".claude/kit.toml").split())
    assert words < 250, f"kit.toml template is {words} words"
