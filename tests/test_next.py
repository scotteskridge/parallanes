"""`kit next`: the facts `/next` words (decision 63): where this folder is, lanes, plans, backlog."""
import pytest

from helpers import git, make_repo, run_cli, write
from kitlib import next_facts
from kitlib.config import load
from lane_helpers import LANES_TOML, lane_dir, lanes_repo

PLAN = """# Export CSV

**Status:** {status}
**Left to do:** the download button
**Branch / PR:** `core/export` · PR link once open

## Goal
"""

ITEM = """---
status: {status}
lane: {lane}
size: {size}
{extra}---
# {title}

Why it matters.
"""


def plan(root, name, status="Approved"):
    return write(root, f"docs/plans/{name}", PLAN.format(status=status))


def item(root, slug, status="next", lane="any", size="M", title="Do a thing", extra=""):
    return write(root, f"docs/backlog/{slug}.md", ITEM.format(status=status, lane=lane, size=size,
                                                               title=title, extra=extra))


# ---- plans -------------------------------------------------------------------------------------

def test_plans_read_title_status_and_left_to_do(tmp_path):
    plan(tmp_path, "2026-10-05-export.md", "In progress")
    found, problems = next_facts.plans(tmp_path)
    assert problems == []
    assert [(p.path, p.title, p.status, p.left) for p in found] == [
        ("docs/plans/2026-10-05-export.md", "Export CSV", "In progress", "the download button")
    ]


def test_plans_skip_readme_template_and_finished(tmp_path):
    write(tmp_path, "docs/plans/README.md", "# Plans\n\n**Status:** Draft\n")
    write(tmp_path, "docs/plans/_TEMPLATE.md", PLAN.format(status="Draft | Approved | In progress | Done"))
    plan(tmp_path, "finished/2026-01-01-old.md", "Done")
    plan(tmp_path, "2026-10-05-export.md", "Draft")
    found, problems = next_facts.plans(tmp_path)
    assert [p.path for p in found] == ["docs/plans/2026-10-05-export.md"]
    assert problems == []


def test_plans_sorted_draft_first_and_done_last(tmp_path):
    plan(tmp_path, "a.md", "Done")
    plan(tmp_path, "b.md", "In progress")
    plan(tmp_path, "c.md", "Draft")
    plan(tmp_path, "d.md", "Approved")
    found, _ = next_facts.plans(tmp_path)
    assert [p.status for p in found] == ["Draft", "Approved", "In progress", "Done"]


@pytest.mark.parametrize("status", ["Draft | Approved | In progress | Done", "Finished", ""])
def test_a_plan_with_an_unknown_or_unset_status_is_a_problem_not_hidden(tmp_path, status):
    plan(tmp_path, "2026-10-05-export.md", status)
    found, problems = next_facts.plans(tmp_path)
    assert found == []
    assert len(problems) == 1 and "docs/plans/2026-10-05-export.md" in problems[0]


def test_a_plan_without_a_status_line_is_a_problem(tmp_path):
    write(tmp_path, "docs/plans/notes.md", "# Notes\n\nNo status here.\n")
    found, problems = next_facts.plans(tmp_path)
    assert found == [] and "no **Status:** line" in problems[0]


def test_no_plans_folder_is_not_an_error(tmp_path):
    assert next_facts.plans(tmp_path) == ([], [])


# ---- backlog -----------------------------------------------------------------------------------

def test_backlog_reads_headers_and_titles(tmp_path):
    item(tmp_path, "export-csv", status="now", lane="core", size="S", title="Export CSV")
    found, problems = next_facts.backlog(tmp_path, ["core", "api"])
    assert problems == []
    entry = found[0]
    assert (entry.slug, entry.title, entry.status, entry.lane, entry.size, entry.blocked_by) == (
        "export-csv", "Export CSV", "now", "core", "S", None)


def test_backlog_skips_readme_template_and_done(tmp_path):
    write(tmp_path, "docs/backlog/README.md", "# Backlog\n")
    write(tmp_path, "docs/backlog/_TEMPLATE.md", ITEM.format(status="idea", lane="any", size="M",
                                                             title="Short imperative title", extra=""))
    item(tmp_path, "done/old-thing", status="now")
    item(tmp_path, "real")
    found, problems = next_facts.backlog(tmp_path, [])
    assert [i.slug for i in found] == ["real"] and problems == []


def test_backlog_sorted_by_status_then_slug(tmp_path):
    item(tmp_path, "b-idea", status="idea")
    item(tmp_path, "z-now", status="now")
    item(tmp_path, "a-later", status="later")
    item(tmp_path, "a-next", status="next")
    item(tmp_path, "a-now", status="now")
    found, _ = next_facts.backlog(tmp_path, [])
    assert [i.slug for i in found] == ["a-now", "z-now", "a-next", "a-later", "b-idea"]


def test_blocked_by_an_item_that_is_done_says_so(tmp_path):
    item(tmp_path, "done/schema", status="now")
    item(tmp_path, "export", extra="blocked_by: schema\n")
    item(tmp_path, "report", extra="blocked_by: export\n")
    found, _ = next_facts.backlog(tmp_path, [])
    by_slug = {i.slug: i for i in found}
    assert by_slug["export"].blocked_by == "schema" and by_slug["export"].blocker_done
    assert by_slug["report"].blocked_by == "export" and not by_slug["report"].blocker_done


@pytest.mark.parametrize("text, reason", [
    ("# No header\n", "no header"),
    ("---\nstatus: now\nlane: any\n# never closed\n", "no header"),
    ("---\nstatus: soon\nlane: any\nsize: M\n---\n# T\n", "status"),
    ("---\nstatus: now\nlane: any\nsize: XL\n---\n# T\n", "size"),
    ("---\nstatus: now\nsize: M\n---\n# T\n", "lane"),
    ("---\nstatus: now\nlane: web\nsize: M\n---\n# T\n", "lane"),
    ("---\nstatus: now\nlane: any\nsize: M\nowner: sam\n---\n# T\n", "owner"),
])
def test_a_malformed_backlog_item_is_reported_not_hidden(tmp_path, text, reason):
    write(tmp_path, "docs/backlog/broken thing.md", text)
    item(tmp_path, "fine")
    found, problems = next_facts.backlog(tmp_path, ["core"])
    assert [i.slug for i in found] == ["fine"]
    assert len(problems) == 1
    assert "docs/backlog/broken thing.md" in problems[0] and reason in problems[0]


def test_backlog_header_tolerates_a_bom_and_crlf(tmp_path):
    path = tmp_path / "docs" / "backlog" / "win.md"
    path.parent.mkdir(parents=True)
    path.write_bytes("﻿---\r\nstatus: now\r\nlane: any\r\nsize: S\r\n---\r\n# Windows\r\n".encode("utf-8"))
    found, problems = next_facts.backlog(tmp_path, [])
    assert problems == [] and found[0].title == "Windows"


# ---- the whole answer --------------------------------------------------------------------------

def test_next_in_a_project_without_lanes(tmp_path):
    repo = make_repo(tmp_path)
    plan(repo, "2026-10-05-export.md", "Draft")
    item(repo, "export-csv", status="now", title="Export CSV")
    write(repo, "src/x.py", "x = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    write(repo, "src/x.py", "x = 2\n")
    result = run_cli(repo, "next", "--offline")
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "Here: not a lane" in out and "1 uncommitted" in out
    assert "Lanes: none configured" in out
    assert "Draft · docs/plans/2026-10-05-export.md · Export CSV" in out
    assert "now · export-csv · Export CSV · lane any · size M" in out
    assert "Problems" not in out


def test_next_reports_problems_with_a_zero_exit(tmp_path):
    # Problems are facts for /next to pass on, not a failure of the command.
    repo = make_repo(tmp_path)
    write(repo, "docs/backlog/broken.md", "# no header\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    result = run_cli(repo, "next", "--offline")
    assert result.returncode == 0, result.stderr
    assert "Problems:" in result.stdout and "docs/backlog/broken.md" in result.stdout


def test_next_in_a_repo_with_no_commits_yet(tmp_path):
    repo = make_repo(tmp_path)
    item(repo, "first", status="now")
    result = run_cli(repo, "next", "--offline")
    assert result.returncode == 0, result.stderr
    assert "Here: not a lane · no commits yet" in result.stdout
    assert "first" in result.stdout


def test_next_without_kit_toml_fails_loudly(tmp_path):
    repo = make_repo(tmp_path, config=None)
    result = run_cli(repo, "next", "--offline")
    assert result.returncode == 2
    assert "kit.toml" in result.stderr


@pytest.mark.slow
def test_next_in_a_lane_names_the_lane_and_reads_the_lanes_own_docs(tmp_path):
    repo = lanes_repo(tmp_path, config=LANES_TOML)
    assert run_cli(repo, "lanes", "create", "core").returncode == 0
    lane = lane_dir(repo, "core")
    item(lane, "lane-only", status="now", lane="core")
    item(repo, "main-only", status="now")
    result = run_cli(lane, "next", "--offline")
    assert result.returncode == 0, result.stderr
    assert "Here: lane core" in result.stdout
    assert "lane-only" in result.stdout and "main-only" not in result.stdout
    assert "core .claude/worktrees/core (this folder)" in result.stdout
    assert "api .claude/worktrees/api · not created" in result.stdout


@pytest.mark.slow
def test_next_in_the_main_checkout_of_a_lanes_project(tmp_path):
    repo = lanes_repo(tmp_path, config=LANES_TOML)
    result = run_cli(repo, "next", "--offline")
    assert result.returncode == 0, result.stderr
    assert "Here: main checkout · main" in result.stdout


def test_lane_names_come_from_the_config(tmp_path):
    repo = make_repo(tmp_path, config=LANES_TOML)
    item(repo, "x", lane="api")
    found, problems = next_facts.backlog(repo, [lane.name for lane in load(repo).lanes])
    assert problems == [] and found[0].lane == "api"
