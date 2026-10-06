"""The reviewer subagent and its checklists (plan 06, decisions 54–60).

The agent is prose, so these tests pin what code can check: it stays read-only, the checklists keep
stable IDs, a pack checklist is picked up by being in the folder, and this repo's dogfood copies
can't drift from the payload.
"""
import re
from pathlib import Path

import pytest

from helpers import ROOT

KIT_OWNED = ROOT / "payload" / "kit-owned" / ".claude"
AGENT = KIT_OWNED / "agents" / "reviewer.md"
REVIEW = KIT_OWNED / "review"
PROJECT_TEMPLATE = ROOT / "payload" / "templates" / ".claude" / "review" / "project.md.tmpl"
STANDARDS = ROOT / "payload" / "templates" / "docs" / "CODE-STANDARDS.md.tmpl"

READ_TOOLS = {"Read", "Grep", "Glob", "Bash"}  # Bash only through the reviewer-bash hook
HOOK_COMMAND = "command: 'sh \"$CLAUDE_PROJECT_DIR/.claude/kit/hook\" reviewer-bash'"
# This repo runs the kit from payload/, so its copy's hook points there (decision 60).
DOGFOOD_HOOK_COMMAND = "command: 'sh \"$CLAUDE_PROJECT_DIR/payload/kit-owned/.claude/kit/hook\" reviewer-bash'"


def frontmatter(text: str) -> tuple[dict, str]:
    """Top-level single-line `key: value` fields, plus the raw block (for the nested hooks map)."""
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "no frontmatter"
    fields = {}
    for line in match.group(1).splitlines():
        if line and not line[0].isspace():
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields, match.group(1)


def checklist_ids(path: Path) -> tuple[str, list[tuple[str, int]]]:
    """(the prefix declared in the heading, [(prefix, number)] of every item in order)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    declared = re.match(r"# .+\(prefix ([A-Z]+)\)$", lines[0])
    assert declared, f"{path.name}: first line must be '# <title> (prefix X)'"
    items = [(m.group(1), int(m.group(2))) for line in lines if (m := re.match(r"([A-Z]+)(\d+)\. \*\*", line))]
    return declared.group(1), items


def assert_well_numbered(path: Path):
    prefix, items = checklist_ids(path)
    assert items, f"{path.name}: no checks"
    assert {p for p, _ in items} == {prefix}, f"{path.name}: every ID must use prefix {prefix}"
    assert [n for _, n in items] == list(range(1, len(items) + 1)), f"{path.name}: IDs must run 1, 2, … with no gaps"


def test_agent_frontmatter():
    fields, _ = frontmatter(AGENT.read_text(encoding="utf-8"))
    assert fields["name"] == "reviewer"
    assert "Use after the tests pass" in fields["description"]
    assert fields["model"] in {"opus", "sonnet", "haiku", "inherit"}  # an alias, never a dated ID


def test_agent_is_read_only():
    fields, block = frontmatter(AGENT.read_text(encoding="utf-8"))
    tools = {tool.strip() for tool in fields["tools"].split(",")}
    assert tools == READ_TOOLS
    assert "permissionMode" not in fields  # nothing that could loosen the caller's permissions
    # The exact block: the command under PreToolUse with the Bash matcher, not just somewhere.
    # A timeout lets the call through, so it is generous (a cold Windows Python start is slow).
    hooks = block[block.index("hooks:"):]
    assert hooks == (
        "hooks:\n"
        "  PreToolUse:\n"
        "    - matcher: \"Bash\"\n"
        "      hooks:\n"
        "        - type: command\n"
        f"          {HOOK_COMMAND}\n"
        "          timeout: 30"
    )


def test_agent_reads_status_without_taking_the_index_lock():
    """`git status` may rewrite .git/index in the author's folder while they keep working."""
    body = AGENT.read_text(encoding="utf-8")
    assert "`git --no-optional-locks status --short`" in body
    assert "`git status" not in body


def test_universal_checklist_is_well_numbered():
    assert_well_numbered(REVIEW / "universal.md")
    assert checklist_ids(REVIEW / "universal.md")[0] == "U"


def test_kit_owned_review_folder_holds_only_checklists():
    for path in REVIEW.iterdir():
        assert path.suffix == ".md"
        assert_well_numbered(path)


def test_stack_checklist_mechanism(tmp_path):
    """A pack adds a file with its own prefix; the agent reads the whole folder, not named files."""
    pack = tmp_path / "unity.md"
    pack.write_text("# Unity checks (prefix UN)\n\nUN1. **Scenes.** x\nUN2. **Meta files.** y\n", encoding="utf-8")
    assert_well_numbered(pack)
    gap = tmp_path / "gap.md"
    gap.write_text("# Gap checks (prefix G)\n\nG1. **A.** x\nG3. **B.** y\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        assert_well_numbered(gap)
    body = AGENT.read_text(encoding="utf-8")
    assert "**Every** `*.md` file in `.claude/review/`" in body


def test_project_template_numbers_its_examples_the_same_way():
    text = PROJECT_TEMPLATE.read_text(encoding="utf-8")
    assert text.startswith("# Project checks (prefix P)\n")
    assert re.search(r"^P1\. \*\*", text, re.MULTILINE)


def test_report_shape_is_in_the_agent():
    body = AGENT.read_text(encoding="utf-8")
    for heading in ("## Review: ", "**Verdict:** ready | fix first", "### Findings", "### Checks run", "### Outside this change"):
        assert heading in body


def test_severities_match_code_standards():
    """The agent quotes §6; if the standards change, the agent must change with them."""
    standards = STANDARDS.read_text(encoding="utf-8")
    severities = re.findall(r"^- (🔴|🟠|🟡) (\*\*.+)$", standards, re.MULTILINE)
    assert len(severities) == 3
    body = AGENT.read_text(encoding="utf-8")
    for emoji, text in severities:
        assert f"- {emoji} {text}" in body


def test_kit_owned_files_are_lf():
    for path in [AGENT, *REVIEW.iterdir(), PROJECT_TEMPLATE]:
        assert b"\r\n" not in path.read_bytes(), path


def test_dogfood_copies_match_the_payload():
    agent_copy = (ROOT / ".claude" / "agents" / "reviewer.md").read_text(encoding="utf-8")
    assert agent_copy.replace(DOGFOOD_HOOK_COMMAND, HOOK_COMMAND) == AGENT.read_text(encoding="utf-8")
    assert DOGFOOD_HOOK_COMMAND in agent_copy
    universal_copy = ROOT / ".claude" / "review" / "universal.md"
    assert universal_copy.read_bytes() == (REVIEW / "universal.md").read_bytes()


def test_this_repos_project_checklist_is_well_numbered():
    assert_well_numbered(ROOT / ".claude" / "review" / "project.md")
