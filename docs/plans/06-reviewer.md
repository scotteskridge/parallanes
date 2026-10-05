# 06 — Reviewer

**Status:** Draft
**Branch / PR:** `plan/06-reviewer` · PR link once open
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
- [ ] Tests above pass locally and in CI (Windows + Ubuntu)
- [ ] Live check done and verified, or its gaps recorded in ARCHITECTURE §15
- [ ] Reviewer report attached to the PR; every 🔴 fixed
- [ ] CHANGELOG, ROADMAP, ARCHITECTURE and decisions log updated where this plan changed them

## Notes after implementation
<!-- Filled in at wrap-up: what changed from the plan and why. -->
