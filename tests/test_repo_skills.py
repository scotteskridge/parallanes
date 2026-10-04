"""This repo's own skills (.claude/skills/) must be well-formed, and read-only ones must stay read-only."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"

# Tools a read-only skill may be granted without asking: nothing here can change files, refs or PRs.
READ_ONLY_TOOLS = re.compile(
    r"^(Read|Grep|Glob"
    r"|Bash\(git (status|branch|log|show|diff|rev-parse) \*\)"
    r"|Bash\(gh pr (list|view|checks) \*\))$"
)


def frontmatter(path: Path) -> dict:
    match = re.match(r"---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.DOTALL)
    assert match, f"{path} has no frontmatter"
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"')
    return fields


def skill_files():
    return sorted(SKILLS.glob("*/SKILL.md"))


def test_skills_have_a_name_matching_their_folder_and_a_description():
    assert skill_files()
    for path in skill_files():
        fields = frontmatter(path)
        assert fields.get("name") == path.parent.name, path
        assert len(fields.get("description", "")) > 40, f"{path}: description too thin to trigger on"


def test_next_skill_is_granted_only_read_only_tools():
    tools = re.findall(r"\S+\([^)]*\)|\S+", frontmatter(SKILLS / "next" / "SKILL.md")["allowed-tools"])
    assert tools
    for tool in tools:
        assert READ_ONLY_TOOLS.match(tool), f"/next is granted a tool that can change things: {tool}"


def test_next_skill_ends_with_a_recommended_prompt():
    assert "**Recommended prompt:**" in (SKILLS / "next" / "SKILL.md").read_text(encoding="utf-8")
