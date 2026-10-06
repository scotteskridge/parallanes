# 06 — Reviewer

**Status:** Done
**Branch / PR:** `plan/06-reviewer` · https://github.com/scotteskridge/claude-code-lanes-starter/pull/10
**Builds on:** plan 01 (`CODE-STANDARDS.md` severities, `WORKFLOW.md`, template rendering and
tests); plan 03 (protected paths, which the reviewer flags); ARCHITECTURE §5 (layers), §9 (the
reviewer), §11 (packs carry a reviewer checklist); decisions 7 (kit-owned vs project-owned), 16
(evidence, not claims)

## Goal
An installed project has a `reviewer` subagent that reviews the current change in a fresh context,
against the project's own rules and the plan, using numbered checks from three checklists
(universal, project, stack). It changes nothing and returns a report in one fixed shape, which
`/wrap-up` (plan 07) can paste into a PR body and act on.

## Out of scope
- Calling the reviewer from `/wrap-up` and putting the report in the PR: plan 07.
- The Unity stack checklist itself: plan 10. This plan defines the mechanism and tests it with a
  stand-in pack file.
- Installing the files and wiring anything into `settings.json`: plan 08.
- Proving review *quality* on a planted bug at scale: the evals in plan 11. This plan does one
  live check.

## Open questions
1. **Where the checklists live.** *Recommendation:* one folder, `.claude/review/`:
   `universal.md` (kit-owned), `project.md` (project-owned, rendered once from a template with a few
   commented examples) and one `<pack>.md` per installed pack (kit-owned, from the pack). Not under
   `.claude/agents/`: the subagent docs say that folder is scanned recursively, so a checklist
   beside the agent could be taken for an agent definition. The reviewer reads every `*.md` in the folder, so a pack
   adds checks by dropping a file in: no config, no registry.
2. **How checks are numbered.** *Recommendation:* each item has a stable ID with a per-file prefix:
   `U1`… universal, `P1`… project, the pack's own prefix (e.g. `UN1`… for Unity, declared in the
   file's first line). The report cites IDs ("U4: test deleted"), so a finding traces to the rule
   it breaks. Tests enforce unique, gap-free IDs in kit-owned checklists.
3. **What the reviewer reads.** *Recommendation:* the diff of the current task, meaning
   `git diff <merge-base with the integration branch>` plus uncommitted and untracked files (so it
   works before and after the commit), `docs/CODE-STANDARDS.md`, the `.claude/rules/` files whose
   `paths:` match a changed file (read explicitly: path-scoped rules load only when a matching file
   is touched), the plan file if the caller names one, and the
   checklists. It may open any file for context but **judges only changed lines**. Pre-existing
   problems it notices go in a short "Outside this change" list, with no severity, at most three.
   The integration branch comes from `kit.toml` when the caller doesn't pass it. `CLAUDE.md` and
   `AGENTS.md` load into a subagent by default (docs), so the reviewer keeps that (no
   `omitClaudeMd`): it judges against the same rules the author had.
4. **What it may do.** *Recommendation:* read-only, enforced, not just asked for. `tools: Read,
   Grep, Glob, Bash` (an allowlist: no `Edit`/`Write`/`NotebookEdit`). The docs don't say whether
   `tools` accepts `Bash(git diff *)` patterns, so Bash is narrowed by a **`PreToolUse` hook in the
   agent's own frontmatter** (`hooks:` is a documented subagent field) that allows only read-only
   git commands (`diff`, `log`, `show`, `status`, `merge-base`, `rev-parse`, `ls-files`) and blocks
   the rest. That is a small `kit hook reviewer-bash` entry point reusing `kitlib/commands.py`'s
   command parsing, tested like the other hooks. It never runs the tests itself (the caller does and
   passes the result), so a review is fast and has no side effects. *Alternative:* prompt-only
   restriction, no new hook; simpler, but a reviewer that can run `git checkout` isn't read-only.
5. **The report's shape.** *Recommendation:* fixed Markdown, so `/wrap-up` and people read it the
   same way:
   ```
   ## Review: <branch> vs <integration> (<N> files)
   **Verdict:** ready | fix first (<n> 🔴) | needs the owner (design question)
   ### Findings
   1. 🔴 U4 `path:line`: what is wrong. Why it matters. Suggested fix.
   ### Checks run
   U1–U14 · P1–P3 · UN1–UN6 (n/a: U9 no new dependencies)
   ### Outside this change
   ```
   Severities are exactly those in `CODE-STANDARDS.md` §6. A design question the plan didn't settle
   is reported as a finding marked "needs the owner", never settled by the reviewer (AGENTS.md:
   flag undecided design questions). "Over-engineering is a defect too" is a universal check.
6. **Model.** *Recommendation:* `opus`. The reviewer is the one independent check before a human,
   it runs once per task, and missing a bug costs more than the tokens. Projects can change it in a
   copy (kit-owned files are replaced on update, decision 7).
7. **Does this repo use its own reviewer?** *Recommendation:* yes, from this plan on. Copy
   `payload/kit-owned/.claude/agents/reviewer.md` and the universal checklist into this repo's
   `.claude/`, with a test that the copies match the payload byte for byte, so dogfooding can't
   drift. Our existing review step (a general-purpose subagent given a prompt) then becomes "use the
   `reviewer` agent", and its reports show the kit's reviewer at work in every PR after this one.
   The alternative, keeping our ad-hoc reviewer, means the kit's reviewer is never used for real
   until plan 11. Its frontmatter hook needs the kit CLI, which this repo runs from
   `payload/kit-owned/.claude/kit/cli.py`; the copy's hook command differs only in that path, and the
   match test allows exactly that difference. Unknown, checked live: whether Claude Code also
   discovers the agent under `payload/kit-owned/.claude/agents/` (the docs don't say); if it does,
   the two would share a name.

## Reuse
- `payload/templates/docs/CODE-STANDARDS.md.tmpl`: the standards and severities the reviewer cites;
  the universal checklist points at it rather than repeating it.
- `payload/templates/docs/ai/WORKFLOW.md.tmpl` (rows "Independent reviewer", §6 "Reviewing the
  agent's work") and `AGENTS.md.tmpl` (finishing step): updated to name the checklists.
- `tests/test_repo_skills.py`: the frontmatter parser and the read-only-grants idea, reused for the
  agent file's `tools` list.
- `tests/test_templates.py`: rendering, LF endings, relative-link checks; extended to the new
  template.
- `kitlib/config.py`: where the reviewer's caller finds `integration_branch` (no code change
  expected).
- This repo's review prompts from plans 03–05 (the 🔴/🟠/🟡 format, "reproduce the bug") as the
  starting point for the agent's instructions.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `payload/kit-owned/.claude/agents/reviewer.md` | New | The subagent: frontmatter (name, description, tools, model) and instructions (questions 3–5) |
| `payload/kit-owned/.claude/review/universal.md` | New | Universal checks `U1`… (question 2) |
| `.../kitlib/reviewer_hook.py`, `cli.py` | New / Edit | `kit hook reviewer-bash`: allow read-only git, block the rest (question 4) |
| `payload/templates/.claude/review/project.md.tmpl` | New | Project checklist `P1`…, with commented examples |
| `payload/templates/docs/ai/WORKFLOW.md.tmpl`, `AGENTS.md.tmpl`, `CODE-STANDARDS.md.tmpl` | Edit | Point at the reviewer and the checklist folder |
| `.claude/agents/reviewer.md`, `.claude/review/universal.md` | New | This repo's dogfood copies (question 7) |
| `tests/test_reviewer.py` | New | See Tests |
| `docs/ARCHITECTURE.md` §4, §9, §11 | Edit | Checklist folder and IDs |

## Steps
1. Tests then code: `kit hook reviewer-bash`.
2. Tests first: agent frontmatter, read-only tools, checklist ID rules, the stack-file mechanism,
   copies matching the payload, the report shape. Then the universal checklist, the project
   template and the agent file until they pass.
3. Template and doc edits; render tests.
4. Live check: in this repo, give the reviewer a scratch branch with planted defects (a deleted
   test, a swallowed exception, an unneeded abstraction, a stand-in pack check) and record which it
   finds, its report shape, and that it changed nothing (`git status` before and after). A
   read-only subagent verifies the evidence.
5. Fresh-context review (by the new reviewer and, for this plan only, the usual general-purpose
   one too, so the two can be compared), fix findings with tests, review fixes until no 🔴, open
   the PR.

## Tests
| Test | Proves |
| --- | --- |
| `test_reviewer_agent_frontmatter` | `name: reviewer`, a description that says when to use it, `model` is an alias, and the file parses |
| `test_reviewer_is_read_only` | `tools` lists only read tools; no `Edit`, `Write`, `NotebookEdit` |
| `test_checklist_ids` | Kit-owned checklists: every item has an ID, prefixes match the file, unique, no gaps |
| `test_stack_checklist_mechanism` | A stand-in `<pack>.md` with its own prefix passes the same rules; the agent's instructions read the whole folder rather than naming files |
| `test_report_shape_documented` | The agent file holds the report headings and the three severities, matching `CODE-STANDARDS.md` §6 |
| `test_hook_reviewer_bash` | Recorded hook JSON: read-only git commands allowed; `git checkout`, `git commit`, `rm`, chained or substituted commands (`git diff; rm x`, `$(...)`) blocked; paths with spaces; a broken input fails closed (this hook guards a read-only promise, so it does not fail open) |
| `test_dogfood_copies_match` | This repo's `.claude/` copies equal the payload files, except the hook command's CLI path |
| `test_templates` (extended) | `project.md.tmpl` renders, is LF, its links resolve |

## Done when
- [x] Tests above pass locally (801 passed) and in CI (Windows + Ubuntu, Python 3.11 + 3.13)
- [x] Live check done and verified, or its gaps recorded in ARCHITECTURE §15
- [x] Reviewer report attached to the PR; every 🔴 fixed
- [x] CHANGELOG, ROADMAP, ARCHITECTURE and decisions log updated where this plan changed them

## Notes after implementation
Changes from the plan:
- **A launcher for the hook** (decision 57): the frontmatter hook runs `sh
  "$CLAUDE_PROJECT_DIR/.claude/kit/hook" reviewer-bash`. `.claude/kit/hook` takes Python from
  `.claude/kit/python-path` (as the pre-commit hook does), because a kit-owned file can't hold a
  machine's interpreter path, and turns any failure into exit 2. This repo's copy of the agent
  points at `payload/kit-owned/.claude/kit/hook`, with a gitignored `python-path` beside it.
- **The guard is stricter than "read-only git"**: it refuses `<`, `>` and globs outside quotes,
  and `$` and backticks outside single quotes (so `$(git merge-base ...)` is blocked; the agent is told to use
  `git diff <base>...HEAD`), a path before `git`, and `--output`, `--ext-diff` and `git grep -O`,
  which write files or run programs from otherwise read-only commands. It allows `cd <folder>`.
- **`AGENTS.md.tmpl` left as is:** its finishing step already says "an independent review", and
  the checklists are named where the reviewer and the owner read them (`WORKFLOW.md`,
  `CODE-STANDARDS.md`); the template's line budget is tight.
- **This repo's own `.claude/review/project.md`** (P1–P5: stdlib only, Windows first, hook failure
  policy, never overwrite, the trail) so the dogfood reviewer checks what matters here.

**Reviews.** Round 1 ran two reviewers on the same commit: the kit's own `reviewer` (its first real
use) and the usual general-purpose one. Both found the same hole independently: `git grep -O<cmd>`
(and `-nO<cmd>`) runs a program and got past the guard; the general-purpose reviewer reproduced it
(`git grep "-Omkdir pwned"` made the folder). Every fix has a test; the new ones failed on the old
code, except two that pin behaviour that was already right but untested (the launcher turning a
crash into exit 2, and the import fallback blocking for this hook).
- *Round 1* (1 🔴, 4 🟠, 9 🟡 across both): `-O` attached or clustered (🔴); untested launcher crash
  path and import fallback; a 10 s timeout that lets the call through (now 30 s, and in §15); a
  repo-local file named `git` passed as git; `$ < >` refused even inside single quotes and `@{1}`
  refs split as commands (false blocks); a missing `tool_name` let the call through; "no pipes" in
  the docs while pipes between read-only git commands pass (the docs now say every command in a
  chain must be read-only git); the hook test was a substring check; `git status` could lock the
  author's index (the agent now uses `--no-optional-locks`); `AGENTS.md.tmpl` not edited (see
  above). One question for the owner: `project.md.tmpl` promised that `/onboard` and `/wrap-up`
  propose `P` checks, which plan 07 hasn't decided; the promise is removed and the question is in
  §15 for plan 07.
- *Round 2* (the fix commit, by this repo's own reviewer with the guard active; it ran in this repo
  by accident when the scratch rebuild failed, and changed nothing): 4 🟡. Unquoted globs expand
  after the check (a branch adding a file named `--output=AGENTS.md` plus `git diff main...HEAD *`
  would overwrite it): now refused. The index lock isn't enforced, only instructed (recorded in
  decision 57). This repo has no `docs/CODE-STANDARDS.md` (its `project.md` now says where the
  standards are). A stale note here. The guard blocked one command it tried (`git check-attr`).
- *Round 3* (the glob fix, by this repo's reviewer): ready, 5 🟡: ARCHITECTURE §9 and a plan note
  lagged the code, the block message advised quoting for a redirect too, two over-long lines;
  plus `HEAD^{tree}` blocked like `@{1}` was (now allowed) and an untested escaped glob (now pinned).
- *From the live-check verifier:* the successful review ran before the folder was trusted, so the
  guard wasn't active, and the reviewer's own first commands began with `cd "<repo>" &&`, which the
  guard refused. `cd <folder>` is now allowed and the agent is told the shell starts at the root.

**Live check** (Windows, Claude Code 2.1.284, headless `claude -p`, a throwaway project laid out
as the kit installs it, in a path with a space; script and outputs kept in the session scratchpad):
- *Review:* on a branch with five planted defects, the reviewer found all five with the right
  check IDs (U3 deleted test, U4 swallowed exception, U8 needless factory, U7 duplicated logic, and
  DM1 from a stand-in pack checklist it found by reading the folder), used the report shape, and
  also flagged the new checklist file itself for the owner (U10). The repo's status and HEAD were
  unchanged afterwards.
- *Guard:* asked to run `git checkout -b probe`, the reviewer refused on its instructions alone, so a
  probe agent with the reviewer's exact frontmatter and neutral instructions tested the hook.
  **First finding:** in an untrusted folder Claude Code skips an agent's frontmatter hooks; the
  debug log says so, the agent still runs, and `git checkout -b probe` went through. After the owner
  accepted the trust dialog, the hook blocked `git checkout -b probe`, `git stash list`, a redirect
  and a `cd ... && ...; echo $?` with exit 2, allowed `git diff main...HEAD --stat`, and nothing in
  the repo changed. Recorded in ARCHITECTURE §15 for plans 08 and 11.
- *Review with the guard active* (after the round 1 and 2 fixes, folder trusted, the debug log
  shows "Registered 1 frontmatter hook(s) from agent 'reviewer'"): all five planted defects found
  again, report in shape, repo status and HEAD unchanged. The guard blocked one call, the
  reviewer's own `cat ... 2>/dev/null` (a redirect); it went on with Read.
- *Discovery:* with the payload's copy temporarily renamed, only this repo's own `reviewer` was
  listed: Claude Code doesn't discover `payload/kit-owned/.claude/agents/`, so the two copies don't
  clash.
- *Not shown live:* macOS and Linux, Windows without Git Bash (`sh` missing: the guard fails open,
  §15), and `/wrap-up` calling the reviewer (plan 07).
