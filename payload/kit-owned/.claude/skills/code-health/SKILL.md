---
name: code-health
description: "Audit the whole codebase by area against the project's own rules, write a dated report, and turn the findings the owner picks into backlog items. Not a diff review (that's /code-review): use /code-health every few features or before a milestone. Changes no code."
model: opus
disable-model-invocation: true
argument-hint: "[optional: one area or folder to audit]"
allowed-tools: Bash(sh .claude/kit/kit next) Bash(sh .claude/kit/kit next *) Bash(git status *) Read Grep Glob
---
Code health audit. $ARGUMENTS

You find and report; you fix nothing. Findings the owner picks become backlog items, and fixes go
through the normal loop (`/plan-feature` or a small task).

## 0. Lane check
Run `sh .claude/kit/kit next --offline`. Its first line says where this folder is:
- `Here: lane <name>`: audit the whole project (it reads the lane's own checkout); the report is
  written on a task branch in this lane (step 4).
- `Here: main checkout` (or `a worktree that isn't a lane`): audit freely; before writing, say to
  run step 4 from a lane folder, or stop after showing the findings.
- `Here: not a lane`: audit, then write on a task branch made with git (step 4).
Stop if this folder has changed files (`N changed`): finish that work first (`/wrap-up`).

## 1. Choose the areas
At most six; merge small ones. An argument narrows the audit to that area.
- Lanes in `.claude/kit.toml` (`[[lanes]]`): one area per lane, its `owns` globs.
- Otherwise the `paths:` of each `.claude/rules/*.md` file.
- Otherwise the top-level folders that hold source and tests.
Skip generated, vendored and build folders, and say so under *Not checked*.

## 2. Audit the areas in parallel
Use the Agent tool, one call per area, all in one message so they run in parallel, with model
`sonnet`, in the foreground: wait for every area before step 3. Tell each agent:
- it is read-only: no edits, no commands that change anything;
- its area (the globs), and to read `AGENTS.md`, `docs/CODE-STANDARDS.md`, every
  `.claude/review/*.md` checklist, the `.claude/rules/` files for its paths, and the
  `docs/design/DESIGN.md` sections that cover its area;
- to look for: duplicated logic, hidden errors (swallowed exceptions, silent fallbacks), drift
  from the rules or the design, files past ~300 lines, code without tests, and stale TODOs;
- to return each finding as one line: severity (🔴 fix now, 🟠 fix soon, 🟡 polish), a checklist
  ID (`U4`, `P2`) or the kind of problem, `path:line`, and why it matters; at most ten per area,
  most severe first, and a two-line summary of the area.
Check a sample of the findings yourself (open the line) before reporting them.

## 3. Report to the owner
Show the findings in one list, most severe first, numbered, with a summary. Ask which ones should
become backlog items (suggest the 🔴 and 🟠 ones), and whether to write the report.

## 4. Write, on the owner's yes
Change files with Edit or Write, never shell redirects, `sed -i` or scripts: the hooks that guard
the lane's paths watch only those tools.
1. Make a task branch `health-YYYY-MM-DD` (today's date): in a lane,
   `sh .claude/kit/kit lanes start health-YYYY-MM-DD` (if it refuses, show why and stop); not a
   lane, `git switch -c health-YYYY-MM-DD` from the integration branch.
2. Write `docs/health/YYYY-MM-DD.md` from `report-template.md` in this skill's folder
   (`${CLAUDE_SKILL_DIR}/report-template.md`): every finding, and the backlog slug for each one
   the owner picked.
3. One backlog item per picked finding: `docs/backlog/<slug>.md` from `docs/backlog/_TEMPLATE.md`,
   `status: next` for 🔴 and 🟠, `idea` for 🟡; `lane` is the area's lane or `any`; the finding
   and the report's path in the body.
4. Ask whether to commit ("Code health YYYY-MM-DD: N findings, M backlog items") and finish it
   like any task (`/wrap-up`).
