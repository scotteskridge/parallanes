"""The kit-owned skills (plan 07): well-formed, safe to pre-approve, and naming only what exists.

Skill quality over real sessions is plan 11's evals; these tests hold what a static check can: the
frontmatter, the grants (decision 67), that every `kit` command and path a skill names is real, and
that each skill starts with the lane check (decision 62).
"""
import re
import shlex

import pytest

from helpers import ROOT, frontmatter

PAYLOAD = ROOT / "payload"
SKILLS = PAYLOAD / "kit-owned" / ".claude" / "skills"
REPO_SKILLS = ROOT / ".claude" / "skills"

EXPECTED = {"next", "plan-feature", "implement", "wrap-up", "design", "code-health"}
# User-invoked only (decision 67): they write files, or (code-health) start costly subagents.
CHANGES_THINGS = {"plan-feature", "implement", "wrap-up", "design", "code-health"}
KNOWN_FIELDS = {"name", "description", "model", "effort", "allowed-tools", "disable-model-invocation",
                "argument-hint"}
MODELS = {"opus", "sonnet", "haiku"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}

# Every grant a payload skill may hold. Wildcards only where every form of the command is read-only:
# not `git diff`/`git log` (`--output` writes a file), not `kit lanes` (start/finish change branches).
READ_ONLY_GRANTS = {
    "Read",
    "Grep",
    "Glob",
    "Bash(sh .claude/kit/kit next)",
    "Bash(sh .claude/kit/kit next *)",
    "Bash(sh .claude/kit/kit lanes status)",
    "Bash(sh .claude/kit/kit lanes status *)",
    "Bash(git status *)",
    "Bash(gh pr list *)",
    "Bash(gh pr view *)",
    "Bash(gh pr checks *)",
}

KIT_CALL = re.compile(r"sh \.claude/kit/kit ([^`\n]+?)(?= <<|`|$)", re.MULTILINE)  # a heredoc isn't an argument
PATH_MENTION = re.compile(r"`((?:docs|\.claude)/[^`\s]+)`")


def skill_files():
    return sorted(SKILLS.glob("*/SKILL.md"))


def body(path):
    return path.read_text(encoding="utf-8").split("\n---\n", 1)[1]


def grants(path) -> list[str]:
    return re.findall(r"\w+\([^)]*\)|\w+", frontmatter(path).get("allowed-tools", ""))


def test_the_task_loop_skills_exist():
    assert {path.parent.name for path in skill_files()} == EXPECTED


@pytest.mark.parametrize("path", skill_files(), ids=lambda p: p.parent.name)
def test_skill_frontmatter(path):
    fields = frontmatter(path)
    assert set(fields) <= KNOWN_FIELDS, f"unknown fields {set(fields) - KNOWN_FIELDS}"
    assert fields["name"] == path.parent.name
    assert 40 < len(fields["description"]) <= 1536, "the listing truncates descriptions at 1,536 characters"
    assert fields.get("model", "sonnet") in MODELS, "use a model alias, never a dated ID"
    assert fields.get("effort", "low") in EFFORTS


@pytest.mark.parametrize("path", skill_files(), ids=lambda p: p.parent.name)
def test_side_effect_skills_are_not_model_invoked(path):
    flag = frontmatter(path).get("disable-model-invocation")
    if path.parent.name in CHANGES_THINGS:
        assert flag == "true", f"/{path.parent.name} changes things: only the owner may start it"
    else:
        assert flag in (None, "false"), "read-only skills stay available to 'what's next?'"


@pytest.mark.parametrize("path", skill_files(), ids=lambda p: p.parent.name)
def test_skill_grants_read_only(path):
    for grant in grants(path):
        assert grant in READ_ONLY_GRANTS, f"/{path.parent.name} pre-approves something that can change state: {grant}"


def kit_calls():
    for path in skill_files():
        for match in KIT_CALL.finditer(body(path)):
            yield path.parent.name, match.group(1)


def test_skills_name_kit_commands():
    assert any(skill == "next" and call.startswith("next") for skill, call in kit_calls())
    assert any(skill == "wrap-up" and call.startswith("lanes finish") for skill, call in kit_calls())


@pytest.mark.parametrize("skill, call", list(kit_calls()))
def test_skill_commands_exist(skill, call):
    """Every `sh .claude/kit/kit ...` a skill names parses, flags included (placeholders filled in)."""
    import cli

    words = shlex.split(re.sub(r"<[^>]+>", "x", call))
    try:
        cli.build_parser().parse_args(words)
    except SystemExit:
        pytest.fail(f"/{skill} names `kit {call}`, which the CLI doesn't accept")


def payload_has(rel: str) -> bool:
    rel = rel.rstrip("/")
    return any(candidate.exists() for candidate in (
        PAYLOAD / "kit-owned" / rel,
        PAYLOAD / "templates" / rel,
        PAYLOAD / "templates" / f"{rel}.tmpl",
    ))


def path_mentions():
    for path in skill_files():
        for rel in PATH_MENTION.findall(body(path)):
            if not re.search(r"[<*]|YYYY", rel):  # patterns, not paths
                yield path.parent.name, rel


def test_skills_name_paths():
    assert ("wrap-up", ".claude/agents/reviewer.md") in set(path_mentions())


@pytest.mark.parametrize("skill, rel", sorted(set(path_mentions())))
def test_skill_paths_exist(skill, rel):
    assert payload_has(rel), f"/{skill} names {rel}, which the kit doesn't install"


@pytest.mark.parametrize("path", skill_files(), ids=lambda p: p.parent.name)
def test_skill_step0_lane_check(path):
    text = body(path)
    step0 = re.search(r"^## 0\. .*?(?=^## 1\. )", text, re.MULTILINE | re.DOTALL)
    assert step0, "step 0 is the lane check"
    assert "sh .claude/kit/kit next" in step0.group(0)
    from kitlib import next_facts  # the labels `kit next` really prints

    for case in (f"`Here: {next_facts.HERE_LANE} ", f"`Here: {next_facts.HERE_MAIN}`",
                 f"`{next_facts.HERE_OTHER_WORKTREE}`", f"`Here: {next_facts.HERE_NO_LANES}`"):
        assert case in step0.group(0), f"step 0 must cover {case}"


@pytest.mark.parametrize("path", skill_files(), ids=lambda p: p.parent.name)
def test_every_kit_call_goes_through_the_launcher(path):
    """Otherwise a call slips past test_skill_commands_exist: `python .claude/kit/cli.py`,
    `{{kit_command}}` (not rendered in kit-owned files) or a bare `kit lanes ...`."""
    text = body(path)
    fenced_lines = [line.strip() for block in re.findall(r"^\s*```\n(.*?)^\s*```", text, re.MULTILINE | re.DOTALL)
                    for line in block.splitlines()]
    spans = re.findall(r"`([^`\n]+)`", text) + fenced_lines
    for span in spans:
        if span in ("kit next", "kit lanes start", "kit lanes finish"):
            continue  # the command's name in prose, not a call
        # What identifies the kit, not the interpreter: `python -m pytest` is fine to mention.
        if re.search(r"\.claude/kit/|\bcli\.py\b|\{\{kit_command\}\}", span) or span.startswith("kit "):
            assert span.startswith("sh .claude/kit/kit "), f"/{path.parent.name}: `{span}` doesn't use the launcher"


@pytest.mark.parametrize("path", skill_files(), ids=lambda p: p.parent.name)
def test_skill_prose_lines_fit(path):
    fenced = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        fenced ^= line.strip().startswith("```")
        if not fenced and not line.startswith(("description:", "allowed-tools:")):
            assert len(line) <= 100, f"line {number} is {len(line)} characters"


def test_wrap_up_hands_the_pr_body_to_lanes_finish():
    text = body(SKILLS / "wrap-up" / "SKILL.md")
    # Decision 65: on stdin, never a file (a file outside the lane's paths makes the ownership hook ask).
    assert "lanes finish --title \"<title>\" --body-file - <<'EOF'" in text
    assert "tmp/" not in text
    assert "reviewer" in text


def test_no_name_clash_with_this_repos_own_skills():
    """Claude Code loads payload skills here once a payload file is read (decision 64)."""
    ours = {path.parent.name for path in REPO_SKILLS.glob("*/SKILL.md")}
    assert not ours & {path.parent.name for path in skill_files()}


@pytest.mark.parametrize("path", skill_files(), ids=lambda p: p.parent.name)
def test_skill_files_are_short_lf_and_clean(path):
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    text = raw.decode("utf-8")
    assert len(text.splitlines()) <= 120, "one screen of procedure; move detail to the docs it points at"
    bad = sorted({hex(ord(c)) for c in text if ord(c) < 32 and c not in "\n\t"})
    assert not bad, f"control characters {bad}"


def test_wrap_up_waits_for_the_reviewer():
    """Live run: the reviewer was started in the background and the docs were written before its
    report came back (and the session then left the skill's model)."""
    assert "in the foreground" in body(SKILLS / "wrap-up" / "SKILL.md")


@pytest.mark.parametrize("skill", ["plan-feature", "implement", "wrap-up", "design", "code-health"])
def test_skills_that_write_files_say_edit_or_write(skill):
    """Live run: agents changed files with heredocs, sed and `python -`, which the ownership hook
    (Edit|Write|MultiEdit|NotebookEdit) never sees."""
    assert "with Edit or Write, never shell redirects" in body(SKILLS / skill / "SKILL.md")


def test_wrap_up_commits_rules_after_the_task():
    """Review round 1: a rule written in step 4 would sit uncommitted beside the task's commit."""
    text = body(SKILLS / "wrap-up" / "SKILL.md")
    assert "Write nothing yet" in text
    step6 = text.split("## 6.", 1)[1]
    assert step6.index("commit them on their own") < step6.index("lanes finish")


def test_implement_lists_every_default_shared_path():
    from kitlib.config import DEFAULT_SHARED_PATHS

    text = body(SKILLS / "implement" / "SKILL.md")
    for shared in DEFAULT_SHARED_PATHS:
        assert f"`{shared.removesuffix('**')}`" in text, f"/implement doesn't name {shared} as shared"


# ---- plan 07b: /design and /code-health --------------------------------------------------------

REPORT_TEMPLATE = SKILLS / "code-health" / "report-template.md"


def section(skill: str, heading: str) -> str:
    """The text of one `## N. <heading>` section, found by name so renumbering doesn't break tests."""
    return body(SKILLS / skill / "SKILL.md").split(f". {heading}\n", 1)[1].split("\n## ", 1)[0]


def test_code_health_report_template():
    """Decisions 69, 79: the template sits in the skill's own folder and fixes the finding shape."""
    text = REPORT_TEMPLATE.read_text(encoding="utf-8")
    for part in ("\U0001f534", "\U0001f7e0", "\U0001f7e1", "| Check |", "`path:line`"):
        assert part in text, f"report template lacks {part!r}"
    assert "report-template.md" in body(SKILLS / "code-health" / "SKILL.md")
    assert b"\r\n" not in REPORT_TEMPLATE.read_bytes()


def test_code_health_says_what_it_adds():
    """Decision 78: not a diff review; the description steers Claude away from it for one."""
    description = frontmatter(SKILLS / "code-health" / "SKILL.md")["description"]
    for phrase in ("whole codebase", "dated report", "backlog"):
        assert phrase in description, f"description lacks {phrase!r}"
    assert "/code-review" in description


def test_code_health_audits_in_parallel_on_sonnet_and_writes_on_a_branch():
    text = body(SKILLS / "code-health" / "SKILL.md")
    assert "in parallel" in text and "`sonnet`" in text  # decision 79
    assert "in the foreground" in text  # wait for every area before writing the report
    # Decision 80 (review rounds 1-2): the report is named per lane and area, so two lanes' runs on
    # one day can't collide; the branch leaves the lane out (its `<lane>/` prefix has it already).
    assert "docs/health/YYYY-MM-DD-<lane>-<area>.md" in text and "health-YYYY-MM-DD-<area>" in text
    assert "`all`" in text and "slug" in text  # a folder like `src/payments` isn't a valid task name


def test_code_health_asks_to_write_only_when_it_can():
    """Review round 2: the audit-only paths must not reach the question about writing."""
    assert "audit-only" in section("code-health", "Report to the owner")


def test_code_health_area_agents_are_read_only():
    """Review round 1: "changes no code" can't rest on prompt text alone for agents that can edit."""
    text = body(SKILLS / "code-health" / "SKILL.md")
    assert "`subagent_type: Explore`" in text
    assert "never run the tests, coverage" in text


def test_code_health_without_lanes_audits_the_source():
    """Review round 1: every install ships rules files for docs and tests, so falling back to their
    `paths:` would audit those and skip the source."""
    areas = section("code-health", "Choose the areas")
    assert "top-level folders" in areas and "Not checked" in areas
    assert "only to split" in areas


def test_code_health_stops_before_the_audit_when_it_could_not_write():
    """Review round 1: a folder that can't start a task, or the main checkout, would lose the findings."""
    step0 = body(SKILLS / "code-health" / "SKILL.md").split("## 0.", 1)[1].split("## 1.", 1)[0]
    assert "show the findings and stop" in step0


def test_code_health_branches_before_it_audits():
    """Review round 2, option A: the audit reads exactly the code the report lands on, and a
    refused `lanes start` (unmerged previous work) stops it before any subagent runs."""
    text = body(SKILLS / "code-health" / "SKILL.md")
    branch = text.index("## 1. Start the task branch")
    assert branch < text.index("## 3. Audit the areas in parallel")
    assert "lanes start health-YYYY-MM-DD-<area>" in text[branch:text.index("## 2.")]


def test_code_health_branches_like_plan_feature():
    text = " ".join(body(SKILLS / "code-health" / "SKILL.md").split())  # phrases may wrap
    assert "`Here: not a lane` (no lanes)" in text
    assert "--no-track -c" in text and "origin/<integration branch>" in text  # pr mode, as /plan-feature
    assert "then tell the owner to run `/wrap-up`" in text  # it can't invoke /wrap-up itself


def test_design_follows_the_rules_file():
    """`.claude/rules/design-docs.md` says how a point is settled; /design does exactly that."""
    text = body(SKILLS / "design" / "SKILL.md")
    assert "changes no branches" in text  # decision 81
    assert "never read it whole" in text
    step4 = text.split("## 4.", 1)[1]
    # The order the rules file sets: show the exact DESIGN.md edit, apply on OK, then the log entry.
    exact, log = step4.index("**exact** `DESIGN.md` edit"), step4.index("`docs/design/decisions-log.md`")
    assert exact < step4.index("Apply") < log


def test_design_offers_a_light_way_to_start_a_task():
    """Without lanes, the same branch commands as /plan-feature step 3 (not a stale local base)."""
    text = " ".join(body(SKILLS / "design" / "SKILL.md").split())
    assert "--no-track -c <task> origin/<integration branch>" in text
    assert "from the main checkout, move to a lane" in text.lower()
