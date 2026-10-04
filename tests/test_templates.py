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
        out = render(path.read_text(encoding="utf-8"), values, set(entries))
        assert "{{" not in out.replace("\\{{", ""), f"{installed_name(path)} left braces behind"


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
        assert re.search(r"^paths:", match.group(1), re.MULTILINE), f"{path.name} has no paths:"


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
