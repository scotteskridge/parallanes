# 07b — Skills: design and code health

**Status:** In progress
**Branch / PR:** `plan/07b-design-health` · PR link once open
**Builds on:** plan 07 (skill layout, step-0 lane check, `kit next`, the skill tests in
`tests/test_skills.py`); plan 01 (`docs/design/` templates, `.claude/rules/design-docs.md`); plan 06
(the review checklists and severities); decisions 61, 69, 77; `survey-hoem.md` rows `design` and
`code-health`; backlog `readme-builtins-comparison`, `ship-kit-as-plugin`, `lighten-plan-process`

## Goal
An installed project has two more skills. `/design` settles one design question: it reads one
section, discusses, then records the answer in `DESIGN.md` and the decisions log on the owner's
OK. `/code-health` audits the whole codebase by area, writes a dated report, and turns the
findings the owner picks into backlog items, so they enter the normal loop.

## Out of scope
- `/onboard`: plan 08 (decision 77).
- A setup health check (`kit doctor`): backlog `doctor-and-uninstall`. `/code-health` looks at the
  code, never at the kit's own setup, so the two don't blur.
- Fixing anything `/code-health` finds: findings become backlog items; fixes go through the loop.
- Plugin packaging (backlog `ship-kit-as-plugin`, plan 08). This plan only keeps the move cheap.

## Open questions
1. **What `/code-health` adds over Claude Code's built-ins.** `/code-review`, `/simplify` and
   `/security-review` look at the current change. *Recommendation:* `/code-health` covers what
   they don't: the **whole codebase by area**, at a moment the owner picks (every few features,
   before a milestone), against the project's own rules (`.claude/review/*.md` check IDs,
   `CODE-STANDARDS.md`, `.claude/rules/`, `DESIGN.md`). It produces a **dated report**, and its
   findings become **backlog items**. The skill's description says this, so Claude doesn't pick it
   for a diff review.
2. **How `/code-health` splits the work.** *Recommendation:* one read-only subagent per area, run
   in parallel, each returning findings in a fixed shape (severity 🔴/🟠/🟡, check ID, `path:line`,
   one line on why). Areas come from the lanes' `owns` globs; without lanes, from the
   `.claude/rules/` `paths:`; failing both, from the top-level source folders (`survey-hoem.md`).
   At most six areas; more get merged. The skill runs on `opus`; the area subagents on `sonnet`,
   to keep a full audit affordable. Each area is checked for duplication, hidden errors, drift from
   the rules and design, files past ~300 lines, untested code, and stale TODOs.
3. **Where the report and items land.** Decision 69 says `docs/health/YYYY-MM-DD.md`, from a
   template in the skill's own folder. *Recommendation:* keep that. The report and the backlog
   items the owner picks are committed on a task branch (`health-YYYY-MM-DD`, made the way
   `/plan-feature` makes one), and `docs/health/**` joins the default shared paths. One file per
   run means no merge conflicts (decision 13).
4. **Where `/design` writes.** `DESIGN.md` isn't a shared path, so in a lane the ownership hook
   asks before the edit, and the owner is there to answer. *Recommendation:* leave it that way.
   One design change at a time is worth one prompt. `/design` changes no branches: the edit lands
   with whatever task branch the folder is on. On the integration branch it stops and says to
   start a task first. With no `DESIGN.md` (it's optional), the decision goes only in the
   decisions log, and the skill offers to create the file, but never does so unasked.
5. **A lighter process for this plan** (backlog `lighten-plan-process`, your earlier OK).
   *Recommendation:* five questions at most; one review round, with another only if it finds a 🔴;
   a live check of one headless run per skill in a scratch project. The loop stays: tests first,
   PR, your approval.

Settled without a question: both skills have side effects (files, subagent cost), so both get
`disable-model-invocation: true`. Each calls the kit only once, in step 0 (`kit next`); lanes and
`owns` are read from `.claude/kit.toml` directly, so a move to a plugin's `bin/` changes one line.

## Reuse
- `payload/kit-owned/.claude/skills/*/SKILL.md` (plan 07): step 0, frontmatter, wording rules
  (Edit or Write only, wait for subagents in the foreground).
- `tests/test_skills.py`: every check extends to the new skills by changing `EXPECTED`.
- `payload/templates/.claude/rules/design-docs.md.tmpl`: already says how settling a point works
  (show the exact `DESIGN.md` edit, apply on OK, then a decisions-log entry). `/design` follows it.
- `payload/templates/docs/design/DESIGN.md.tmpl` (`[BUILT]`/`[DIRECTION]`/`[OPEN]` labels) and
  `decisions-log.md.tmpl` (entry format).
- `payload/kit-owned/.claude/review/universal.md` and `project.md.tmpl`: the check IDs findings cite.
- `payload/templates/docs/backlog/_TEMPLATE.md.tmpl`: the items findings become.
- `kitlib/config.py` `DEFAULT_SHARED_PATHS`: gains `docs/health/**` (question 3).

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `payload/kit-owned/.claude/skills/design/SKILL.md` | New | `/design` |
| `payload/kit-owned/.claude/skills/code-health/SKILL.md`, `report-template.md` | New | `/code-health` and its report template |
| `kitlib/config.py`, `kit.toml.tmpl`, ARCHITECTURE §6 | Edit | `docs/health/**` shared by default |
| `tests/test_skills.py`, `tests/test_config_lanes.py` | Edit | New skills; the shared default |
| `payload/templates/docs/ai/WORKFLOW.md.tmpl`, `CLAUDE.md.tmpl` | Edit | Only if the skills differ from what they promise |
| `docs/ARCHITECTURE.md` §4, §9 | Edit | `docs/health/`, the two skill rows |

## Steps
1. Tests first: extend `tests/test_skills.py` (expected skills, side effects, the report
   template exists and has the finding shape) and the shared-paths default; see them fail.
2. Write `/design`, then `/code-health` and its template, until the tests pass.
3. Doc and template edits.
4. Live check in a scratch project laid out as the kit installs it: `/design` on an `[OPEN]`
   section (settle it, then check the `DESIGN.md` edit and the log entry); `/code-health` on a
   project with two lanes and planted problems (a swallowed exception, a duplicated function, an
   over-long file), checking it finds them, writes the report and creates only the items chosen.
5. One review round by this repo's `reviewer`, fixes with tests, PR.

## Tests
| Test | Proves |
| --- | --- |
| `test_the_task_loop_skills_exist` (extended) | `design` and `code-health` ship with the others |
| `test_side_effect_skills_are_not_model_invoked` (extended) | Both are user-invoked only |
| `test_code_health_report_template` | The template exists beside the skill, has the finding shape (severity, check ID, `path:line`), and the skill names it |
| `test_code_health_says_what_it_adds` | The description names the whole codebase and the dated report, so Claude doesn't choose it for a diff |
| `test_design_follows_the_rules_file` | `/design` shows the exact edit before applying it and adds a decisions-log entry |
| `test_default_shared_paths` (extended) | `docs/health/**` is shared by default |
| Existing skill tests | Frontmatter, read-only grants, kit commands and paths exist, step 0, line length |

## Done when
- [ ] Tests above pass locally and in CI (Windows + Ubuntu, Python 3.11 + 3.13)
- [ ] Live check done and verified, or its gaps recorded in ARCHITECTURE §15
- [ ] Reviewer report attached to the PR; every 🔴 fixed
- [ ] CHANGELOG, ARCHITECTURE and decisions log updated where this plan changed them

## Notes after implementation
Changes from the plan:
- **`docs/health/README.md`** (a new template): the path test showed the kit didn't install the
  folder `/code-health` writes to; the README says what the reports are and that findings live in
  the backlog.
- **`/design` stops on a lane between tasks too,** not only on the integration branch: a lane is
  detached then, and an edit there would block the next `lanes start`.
- `/implement` names `docs/health/` among the shared docs (the test from plan 07 requires every
  default shared path).
- No `WORKFLOW.md` or `CLAUDE.md` edits: both already describe the two skills as built.
- **Changed by the reviews** (questions 2 and 3 above describe the plan as approved): without lanes
  the areas are the top-level source folders, never the rules files' paths; the area agents are
  `Explore`; the report is `docs/health/YYYY-MM-DD-<lane>-<area>.md` on branch
  `health-YYYY-MM-DD-<area>`; an audit that can't be saved stops after showing the findings.

**Live check** (Windows, Claude Code 2.1.284, headless `claude -p`; a throwaway project laid out as
the kit installs it, two lanes `core` and `tools`, a `DESIGN.md` with an **[OPEN]** section, three
planted problems; scripts and outputs in the session scratchpad):
- *`/design`* (Opus) on the lane between tasks: read only §2 and the log, gave three options with
  costs and a recommendation, asked three questions, and edited nothing, saying to start a task.
  After `lanes start` and an answer, it showed the exact `DESIGN.md` edit (**[OPEN]** →
  **[DIRECTION]**) and the log entry. The ownership hook asked before the `DESIGN.md` edit
  (decision 81); headless, that ask is a denial, and the skill stopped and waited instead of
  working around it, without writing the log entry first.
- *`/code-health`* (Opus, with Sonnet area agents) from the `tools` lane: two areas from the lanes'
  `owns`; found all three planted problems (U4 swallowed exception, U7 duplicated rounding across
  lanes, U13 a 359-line file) plus real ones (a rounding bug, untested code, a design label that
  didn't match the code), checked a sample itself, and asked. On the answer it ran `lanes start`,
  wrote `docs/health/2026-10-06.md` and exactly the three items picked (one combining two
  findings), and committed on `tools/health-2026-10-06`. `kit next` read the new items' headers
  without problems. No permission denials after the first audit turn, which had one refused
  compound shell command.
- *Not shown live:* the owner approving the `DESIGN.md` prompt in an interactive session, a
  project without lanes or without `DESIGN.md`, macOS/Linux. This run was before the reviews:
  the `Explore` agents, the new names and the non-lane branch commands haven't run live.

**Review** (by this repo's `reviewer`; every finding fixed, tests where a check is cheap; the
`/design` order test passed before the fix, pinning behaviour already right):
- *Round 1* (1 🔴, 4 🟠, 5 🟡): without lanes, `/code-health` took its areas from the rules files,
  which every install ships for docs and tests, so it would never audit the source (🔴; areas are
  now the top-level source folders, rules paths only split one, and uncovered source is listed);
  it audited even when it couldn't write a branch afterwards, and from the main checkout,
  losing the findings (it now stops first, or audits and stops); its non-lane branch didn't start
  from the integration branch as `/plan-feature`'s does; two runs on one day collided on one
  report name (now `<date>-<area>`, `-2` if taken); it told the agent to run `/wrap-up`, which
  only the owner can start; its area agents could edit (now `Explore`, told never to run tests or
  coverage); `/design` offered no light way to start a task without lanes; weak test assertions;
  decision 81 lagged the skill.
- *Round 2* (the fix commit; all ten round-1 fixes confirmed; no 🔴, 1 🟠 for the owner, 6 🟡):
  the report name said one lane for a whole-project audit, and a narrowed folder wasn't a valid
  task name (now `<lane>-<area>` in the report, `<area>` a slug or `all`); the audit-only paths
  still reached the question about writing (now they stop); `/design`'s branch advice differed
  from `/plan-feature`'s and left out the main checkout; `Explore` was called read-only though it
  has Bash; the plan's text and live-check notes lagged the fixes. All fixed. **For the owner:**
  the audit reads the folder as it is, but the report's branch starts from the newer integration
  tip, so a lane that is behind reports `path:line`s that may have moved.
- *Owner's answers after round 2:* option A, the task branch first (decision 83, with a test that
  the branch step comes before the audit); a backlog item for a dedicated `auditor` agent.
