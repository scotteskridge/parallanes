# 07 — Skills: the task loop

**Status:** In progress
**Branch / PR:** `plan/07-skills` · PR link once open
**Builds on:** plan 01 (the templates the skills fill in: plans, backlog, changelog fragments,
decisions log, `WORKFLOW.md`); plans 04–05 (`kit lanes status`, `start`, `sync`, `finish`); plan 06
(the `reviewer` and its report shape); ARCHITECTURE §8 (shared docs), §9 (skills); decisions 7
(kit-owned vs project-owned), 13 (fragments), 26 (this repo's `/next` prototype)

## Goal
An installed project has the skills that run its daily loop: `/next` says what to pick up,
`/plan-feature` turns a request into an approved plan on a task branch, `/implement` builds it
test-first, and `/wrap-up` tests, gets the reviewer's report, writes the changelog fragment and,
on the owner's yes, commits and runs `lanes finish`. Plus `/design`, `/code-health` and
`/onboard`, unless question 1 moves them to a second plan.

## Out of scope
- Copying the skills into a project and wiring `settings.json`: plan 08.
- Evals that measure skill quality over many runs (`claude -p` scenarios): plan 11. This plan
  has static tests and one live run.
- `/sync-state` and `BUILD-STATE.md` (decision 21), `/refactor`, role skills per lane: Later.
- Changing the lane commands themselves (plan 05). Gaps found here become backlog items or §15 rows.

## Open questions
1. **Split the plan?** Seven skills is more than one screen of steps. *Recommendation:* split.
   **07** = the task loop that everything else hangs on: `/next`, `/plan-feature`, `/implement`,
   `/wrap-up`, with their live run. **07b** = `/design`, `/code-health`, `/onboard`. `/onboard`
   writes `kit.toml`, rules files and lanes, so it sits better next to the installer (08) anyway.
   Plans 08–12 keep their numbers. The rest of this file assumes the split; questions 8–9 are
   recorded now so 07b starts from them.
2. **Projects and folders that aren't a lane.** `lanes start`/`finish` refuse outside a lane folder
   (decision 51), but a project may have no `[[lanes]]`, or the owner may work in the main
   checkout. *Recommendation:* the skills handle both, with no new CLI: outside a lane,
   `/plan-feature` creates the task branch with `git switch -c <task>` from the integration branch,
   and `/wrap-up` commits, then (PR mode) proposes `git push -u origin HEAD` and
   `gh pr create --body-file ...` for the owner's yes, or (local mode) stops after the commit and
   says how to merge. Step 0 of every skill says which case it is in.
3. **Gather facts in code, word them in the skill.** `/next` must read lanes, PRs, plan status
   lines and backlog headers, skipping `README.md` and `_TEMPLATE.md` (§15). Done in prose, none of
   that is testable. *Recommendation:* a new `kit next` command (stdlib, read-only, tested like the
   others) prints the facts in a fixed text shape: per lane its branch, state and PR; plans by
   status (`**Status:**` line, `docs/plans/*.md`, not `finished/`); backlog items by `status`,
   `lane`, `size`, `blocked_by`. The skill turns that into the answer and one recommended prompt,
   as this repo's `/next` does. `--offline` as in `lanes status`.
4. **The two `/next`s, and payload skills seen while building the kit** (§15). The skills docs
   say nested `.claude/skills/` folders load "when Claude works on files there", listed with a
   folder prefix (`/apps/web:deploy`); plan 06 found agents under `payload/` are *not* discovered.
   So while we edit the payload, `/payload/kit-owned:wrap-up` may appear in this repo, and could run
   against this repo's layout. *Recommendation:* check it live in step 1. If they appear, rename
   this repo's prototype to `/kit-next` (dev-only, named in two docs) so plain `/next` never means
   two things, and add one line to this repo's `CLAUDE.md` (proposed for your OK): never run a
   payload skill here. Either way, a test fails if a payload skill's name equals one in this
   repo's `.claude/skills/`.
5. **The PR body.** `/wrap-up` passes `--body-file` to `lanes finish` with the plan link, a summary,
   the test result lines and the reviewer's report. *Recommendation:* it writes the file to
   `.claude/kit/tmp/pr-body.md` (plan 08 gitignores `.claude/kit/tmp/`) and deletes it after a
   successful finish; the fragment and commit message stay in the conversation until the owner
   says yes.
6. **"Corrected the same thing twice"** (§15). A skill only sees its own session. *Recommendation:*
   `/wrap-up` looks back over this session and also asks the owner whether anything needed
   correcting more than once. For each such thing it proposes **one** of: a `.claude/rules/` line
   (something the author should know while writing, scoped by `paths:`), a `P` check in
   `.claude/review/project.md` (something the reviewer should catch afterwards, next free number),
   or a `kit.toml` rule-check pattern (a literal pattern that must never appear). It shows the
   exact lines and writes them only on a yes, in a separate commit from the task.
7. **How far skills pre-approve.** *Recommendation:* `allowed-tools` holds only read-only grants
   (`Read`, `Grep`, `Glob`, `kit lanes status`, `kit next`, `git status/diff/log`, `gh pr list/view/checks`),
   so commits, pushes and `lanes finish` still show a permission prompt after the owner's yes in
   chat. Skills that change things have `disable-model-invocation: true` (§9): `/plan-feature`,
   `/implement`, `/wrap-up`. `/next` stays model-invocable ("what's next?"). A test holds both
   rules.
8. *(07b)* **`/onboard` and `P` checks** (§15): propose at most three, each tied to something it
   found in the repo, never written unasked. ARCHITECTURE §9 says it calls `kit check settings`,
   which doesn't exist; it should call `kit settings sync` and `kit lanes create` after approval.
9. *(07b)* **Where `/code-health` writes:** `docs/health/YYYY-MM-DD.md` from a report template kept
   in the skill's own folder (kit-owned), not in `payload/templates/`.

10. **`model` and `effort` in skill frontmatter.** §9 gives each skill a model, and this repo's
    `/next` sets `model: sonnet` and `effort: low`. A docs lookup for this draft didn't find either
    field in the skills reference (it listed them for subagents only), which contradicts what we
    use. *Recommendation:* settle it in step 1 against the docs page itself and a live run; if
    unsupported, drop both from the skills and §9 rather than shipping fields that do nothing.

## Reuse
- `.claude/skills/next/SKILL.md`: the prototype; its output shape and "one recommended prompt".
- `tests/test_repo_skills.py`: frontmatter parser and read-only grant checks, extended to the
  payload skills.
- `kitlib/lane_status.py`, `lane_cli.py`, `config.py`: lane facts and `kit.toml` for `kit next`.
- `kitlib/changelog.py`: already skips `README.md`/`_TEMPLATE.md` in a fragment folder; the same
  rule for backlog and plans.
- `payload/templates/docs/plans/_TEMPLATE.md.tmpl`, `backlog/_TEMPLATE.md.tmpl`,
  `changelog.d/README.md.tmpl`: the files the skills write from.
- `payload/kit-owned/.claude/agents/reviewer.md`: `/wrap-up` calls it and pastes its report.
- `WORKFLOW.md.tmpl` §3 (the daily loop) and `CLAUDE.md.tmpl`: already describe these skills; the
  skills must match what they promise.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `payload/kit-owned/.claude/skills/{next,plan-feature,implement,wrap-up}/SKILL.md` | New | The four skills |
| `.../kitlib/next_facts.py`, `cli.py` | New / Edit | `kit next` (question 3) |
| `tests/test_skills.py`, `tests/test_next.py` | New | See Tests |
| `tests/test_repo_skills.py` | Edit | Name-clash check (question 4) |
| `payload/templates/docs/ai/WORKFLOW.md.tmpl`, `CLAUDE.md.tmpl` | Edit | Only where the skills differ from what they promise |
| `docs/ARCHITECTURE.md` §9, §15; `docs/plans/README.md` | Edit | Skill table, answered rows, the 07b row |

## Steps
1. Live check first: does Claude Code list a skill placed under `payload/kit-owned/.claude/skills/`
   in this repo, and does a skill's `model` field take effect? Settles questions 4 and 10.
2. Tests then code: `kit next` (lanes, plans, backlog, skipped files, offline, no `kit.toml`).
3. Tests first for the skill files (Tests below), then the four `SKILL.md` files.
4. Template and doc edits.
5. Live run in a scratch project laid out as the kit installs it, with one lane, in a path with a
   space: `/next` → `/plan-feature` → approve → `/implement` → `/wrap-up` → `lanes finish` (local
   mode, and PR mode against a scratch GitHub repo if feasible). A read-only subagent verifies the
   evidence. Covers the §15 row "an agent session driving `lanes start`/`finish`".
6. Fresh-context review by this repo's `reviewer`, fix with tests, review fixes until no 🔴, PR.

## Tests
| Test | Proves |
| --- | --- |
| `test_skill_frontmatter` | Every payload skill: `name` = folder, a description that says when to use it, `model` an alias if question 10 keeps it |
| `test_side_effect_skills_not_model_invoked` | `/plan-feature`, `/implement`, `/wrap-up` have `disable-model-invocation: true` |
| `test_skill_grants_read_only` | `allowed-tools` in every payload skill uses only read-only grants (question 7) |
| `test_skill_commands_exist` | Every `kit ...` command a skill names exists in the CLI parser, with those flags |
| `test_skill_paths_exist` | Every template or doc path a skill names exists in the payload |
| `test_skill_step0_lane_check` | Each skill's first step is the lane check, covering lane and non-lane cases |
| `test_no_name_clash` | No payload skill shares a name with this repo's own skills |
| `test_next_*` | `kit next`: lanes and PRs, plan statuses, backlog headers, `README.md`/`_TEMPLATE.md`/`done/`/`finished/` skipped, a malformed header reported not hidden, no lanes, `--offline` |

## Done when
- [ ] Tests above pass locally and in CI (Windows + Ubuntu, Python 3.11 + 3.13)
- [ ] Live run done and verified, or its gaps recorded in ARCHITECTURE §15
- [ ] Reviewer report attached to the PR; every 🔴 fixed
- [ ] CHANGELOG, ROADMAP, ARCHITECTURE and decisions log updated where this plan changed them

## Notes after implementation
Changes from the plan:
- **Question 10 settled by the docs page itself:** `model` and `effort` are skill fields (the docs
  lookup for the draft was wrong). Seen live: `model: haiku` took effect when typed as `/name`, but
  not when Claude ran the skill through the Skill tool (one headless run each).
- **Question 4:** payload skills do load here once a payload file is read: plain names unless they
  clash, then `/payload/kit-owned:next`. This repo's prototype is now `/kit-next`; its own text says
  never to run a payload skill here. The plan's `CLAUDE.md` line is proposed to the owner, not added.
- **A launcher for skills** (decision 71, settled during the build): `sh .claude/kit/kit <command>`,
  because a kit-owned skill can hold neither `{{kit_command}}` nor an interpreter path.
- **The PR body goes on stdin** (`lanes finish --body-file -`, decision 65 changed): the approved
  `.claude/kit/tmp/` file asked on every wrap-up (live run). A small change to plan 05's code.
- **`docs/design/decisions-log.md` became a default shared path** (decision 72) and
  **`.worktreeinclude` copies `python-path` into lanes**: both found in the live run.
- **Question 8 was wrong about `kit check settings`:** it exists (plan 03). Decision 68 corrected.
- Plan file globs (`test_plans.py`, `/kit-next`) accept split plans such as `07b`.
- No template edits were needed: `WORKFLOW.md` and `CLAUDE.md` already describe the loop as built.

**Live run** (Windows, Claude Code 2.1.284, headless `claude -p`, throwaway projects laid out as the
kit installs them, one lane `core`, paths with spaces; scripts and outputs in the session
scratchpad). Permission prompts were stood in for by `--allowedTools` for kit, git and Python.
- *Local mode:* `/next` → `/plan-feature subtract` → approval → `/implement` → `/next` → `/wrap-up`
  → yes. Each skill ran on its model (Sonnet; Opus for `/plan-feature` and the reviewer), `/next`
  gave the right step both times, `/implement` wrote tests first, `/wrap-up` ran the reviewer, named
  the fragment `core-subtract.md` (the plan had guessed `subtract.md`), moved the plan and backlog
  item, asked, then `lanes finish` fast-forwarded `main`. Found: the PR body file and the
  decisions-log edit both hit permission asks (fixed above).
- *PR mode,* after the fixes, with a local bare `origin` and a stand-in `gh` recording its input:
  the same loop; `/wrap-up` and its finish had no permission denials, `gh pr create ...
  --body-file -` received the body as UTF-8 with LF endings only, and the branch reached `origin`.
  `/plan-feature` and `/implement` each had one compound shell command refused (a `$(...)`, a
  `printf >>; sed -i` chain) and carried on with other tools.
- *From the verifier* (read-only subagent, checked the transcripts, not the summaries): all claims
  above confirmed, plus three things the summaries didn't say. `/wrap-up` started the reviewer in
  the background and wrote the docs before its report came back, and the session then ran on Opus,
  not the skill's Sonnet. Agents changed files with heredocs, `sed -i` and `python -`, which the
  ownership hook (Edit/Write only) never sees: `/implement` wrote its tests that way, in the right
  order. The PR run's plan commit also held its decisions-log entry. Fixed in the skills: the
  reviewer runs in the foreground, and the three writing skills say to change files with Edit or
  Write only (tests hold both). Not re-run live after this last fix.
- *Not shown live:* a real GitHub PR, macOS/Linux, the owner clicking real permission prompts, a
  sync conflict during `/wrap-up`, a project without lanes, and the reviewer's guard (the scratch
  folders weren't trusted, so its frontmatter hook was skipped, as recorded in plan 06).
