"""The plans index and the plan files must agree, so the plan trail stays trustworthy."""
import re
from pathlib import Path

PLANS = Path(__file__).resolve().parent.parent / "docs" / "plans"
STATUSES = {"Draft", "Approved", "In progress", "Done"}


def plan_files():
    return sorted(p for p in PLANS.glob("[0-9][0-9]*-*.md"))


def test_every_linked_plan_in_the_index_exists():
    index = (PLANS / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\(([0-9][0-9][a-z]?-[^)]+\.md)\)", index)
    assert links, "the index links no plans"
    for link in links:
        assert (PLANS / link).is_file(), f"index links missing plan {link}"


def test_every_plan_file_is_in_the_index():
    index = (PLANS / "README.md").read_text(encoding="utf-8")
    for plan in plan_files():
        assert f"]({plan.name})" in index, f"{plan.name} is not linked from docs/plans/README.md"


def test_every_plan_has_a_known_status():
    for plan in plan_files():
        match = re.search(r"^\*\*Status:\*\* (.+)$", plan.read_text(encoding="utf-8"), re.MULTILINE)
        assert match, f"{plan.name} has no **Status:** line"
        assert match.group(1).strip() in STATUSES, f"{plan.name} has unknown status {match.group(1)!r}"


def test_index_status_matches_plan_file():
    index = (PLANS / "README.md").read_text(encoding="utf-8")
    for plan in plan_files():
        row = next((line for line in index.splitlines() if f"]({plan.name})" in line), None)
        assert row is not None, f"{plan.name} has no row in docs/plans/README.md"
        match = re.search(r"^\*\*Status:\*\* (.+)$", plan.read_text(encoding="utf-8"), re.MULTILINE)
        assert match, f"{plan.name} has no **Status:** line"
        status = match.group(1).strip()
        assert row.rstrip(" |").endswith(status), f"index row for {plan.name} doesn't say {status!r}"
