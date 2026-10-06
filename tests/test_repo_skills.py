"""This repo's own skills (.claude/skills/) must be well-formed, and read-only ones must stay read-only.

`allowed-tools` pre-approves tools (no permission prompt); it doesn't forbid others, which would
still prompt. So the grant list is what must stay read-only: a wildcard like `git branch *` would
silently pre-approve `git branch -D`.
"""
import re
from pathlib import Path

from helpers import frontmatter

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"

# Every grant a read-only skill may hold. Wildcards only where every form of the command is
# read-only; everything else is an exact command.
READ_ONLY_GRANTS = {
    "Read",
    "Grep",
    "Glob",
    "Bash(git status *)",
    "Bash(git branch -vv)",
    "Bash(git rev-list --left-right --count main...HEAD)",
    "Bash(gh pr list *)",
    "Bash(gh pr checks *)",
    "Bash(gh pr view *)",
}


def grants(skill: str) -> list[str]:
    text = frontmatter(SKILLS / skill / "SKILL.md").get("allowed-tools", "")
    return re.findall(r"\w+\([^)]*\)|\w+", text)


def skill_files():
    return sorted(SKILLS.glob("*/SKILL.md"))


def test_skills_have_a_name_matching_their_folder_and_a_description():
    assert skill_files()
    for path in skill_files():
        fields = frontmatter(path)
        assert fields.get("name") == path.parent.name, path
        assert len(fields.get("description", "")) > 40, f"{path}: description too thin to trigger on"


def test_next_skill_is_granted_only_read_only_tools():
    found = grants("kit-next")
    assert found, "allowed-tools must be a single space-separated line"
    for grant in found:
        assert grant in READ_ONLY_GRANTS, f"/kit-next is pre-approved for something that can change state: {grant}"


def test_next_skill_ends_with_a_recommended_prompt():
    assert "**Recommended prompt:**" in (SKILLS / "kit-next" / "SKILL.md").read_text(encoding="utf-8")


def test_skill_files_have_no_control_characters():
    # Scripted edits can turn "\b" into a backspace; invisible in review, but it breaks the regex.
    for path in skill_files():
        text = path.read_text(encoding="utf-8")
        bad = sorted({hex(ord(c)) for c in text if ord(c) < 32 and c not in "\n\t"})
        assert not bad, f"{path} contains control characters {bad}"
