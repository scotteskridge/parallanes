# Roadmap

Goal: set up a new project with the full agent workflow (rules, skills, hooks, reviewer, parallel
lanes) in a few steps, instead of rebuilding it each time. Generalized from the Hall of Echoing Mirrors
setup (see `survey-hoem.md`). **MVP** = version 1; **Later** = after it's working.
Decisions behind this list: `decisions-log.md`.

## 1. Setup and installation
- **MVP** One-command setup: `install.ps1` (Windows first) and `install.sh` (Mac/Linux), both thin wrappers over one Python script
- **MVP** Interactive questions: project name, one-line description, tech stack, test command, lane names, Unity yes/no
- **MVP** Prerequisite check: git, Python 3.11+, Claude Code; clear message if something is missing
- **MVP** Works on a brand-new folder *or* an existing repo, without overwriting existing files (asks first)
- **MVP** Dry-run mode that lists what it would create before doing anything
- **Later** Non-interactive mode (answers from a config file) for repeat setups
- **Later** Update command: pull newer kit versions into an existing project and show what changed (uses the kit-owned file manifest)
- **Later** Uninstall/removal command

## 2. Core instructions (what the agent reads)
- **MVP** `AGENTS.md` template with the universal rules, read by any coding agent
- **MVP** `CLAUDE.md` template, kept short, importing `@AGENTS.md`: project brief, hard rules, how to check your work, session hygiene, design-doc policy
- **MVP** Placeholders filled in by setup (project name, stack, test command)
- **MVP** Path-scoped rule templates in `.claude/rules/` that load only for matching code areas
- **MVP** Built-in universal rules: search before you create; never hide errors; never weaken, skip or delete tests to pass; one task per session; flag undecided design questions instead of settling them silently; the shell starts at the project root (no `cd` prefixes)
- **MVP** `docs/ai/WORKFLOW.md`: the human guide explaining why each rule exists and the daily loop

## 3. Skills (slash-command workflows)
- **MVP** `/plan-feature`: interviews you, writes a plan file with steps, tests and a done-when checklist
- **MVP** `/implement`: builds one approved plan, test-first
- **MVP** `/wrap-up`: run tests, call the reviewer, update the changelog and build state, draft the commit message
- **MVP** `/code-health`: periodic audit for duplication, hidden errors and drift, written as a dated report
- **MVP** `/design`: design discussion that reads one design-doc section and logs the decision
- **Proposed** `/next`: lane-aware "what's next" (ready / waiting on you / blocked), from the survey
- **Later** `/refactor`, `/sync-state` (keep status docs true), `/workflow` (maintain the kit itself)
- **Later** Role skills per lane (e.g., `/ui-work`, `/writing`) that load only that role's docs
- **MVP** Templates: plan file, decisions log entry, changelog entry, code-health report

## 4. Subagents
- **MVP** `reviewer`: fresh context, sees only the diff, the rules and the plan; numbered checklist; severity levels (fix now / fix soon / polish)
- **MVP** Reviewer checklist split into a universal part plus a stack-specific part (e.g., Unity items)
- **Later** Researcher/explorer subagent for codebase searches that would otherwise clutter the main session
- **Later** Test-writer subagent

## 5. Hooks (automatic enforcement)
- **MVP** Rules-check hook (PostToolUse on Edit/Write): forbidden patterns from per-project TOML (pattern, file glob, message); exits 2 so the agent fixes violations; fails open; ignores comments
- **MVP** Lane-router hook (SessionStart): tells the agent its lane, branch, scope and per-lane tools/port
- **MVP** Protected-paths hook (PreToolUse): blocks edits to read-only folders and dangerous commands (force-push, hard reset); fails closed
- **Later** Stop hook that reminds the agent to run tests if code changed without a test run
- **Later** Formatter/linter hook per stack
- **MVP** All hooks in Python, cross-platform, each with its own tests

## 6. Parallel lanes (the differentiator)
- **MVP** `lanes.toml`: lane name, branch, scope description, owned paths, tool port; plus the integration branch
- **MVP** `lanes create`: branch and git worktree per lane (default `.claude/worktrees/<lane>/`), `.worktreeinclude` for local settings, optional shared auto-memory link
- **MVP** `lanes status`: each lane's branch, ahead/behind the integration branch, uncommitted changes, unpushed work
- **MVP** `lanes sync`: brings the integration branch into each lane
- **MVP** `lanes merge <lane>`: tests pass → fast-forward the integration branch (`git push . HEAD:<branch>`), with conflict guidance
- **MVP** Ownership rules: each lane edits only its owned paths; the hook warns on out-of-lane edits
- **MVP** Per-lane tool instances (e.g., separate Unity Editor + MCP port per lane)
- **Later** Lane handoff notes at session end
- **Later** Push-reminder for commits that exist only locally

## 7. Permissions and safety
- **MVP** `settings.json` template with allow/deny lists (root-anchored patterns, tested)
- **MVP** `.gitignore` / `.gitattributes` templates (`settings.local.json`, caches, `.env`, LF endings, `merge=union` for append-only docs)
- **MVP** Secrets guidance: keys live outside the repo; `.env` never committed
- **Later** Pre-commit secret scan

## 8. Verification and CI
- **MVP** Configurable test command, used by skills and the merge helper ("evidence, not claims")
- **Later** GitHub Actions template for installed projects: tests and rules check on every push and PR
- **Later** Optional test-count and coverage report

## 9. Project documentation scaffolding
- **MVP** `docs/plans/` (+ `finished/`), `docs/CHANGELOG.md`, `docs/BUILD-STATE.md`, `docs/BACKLOG.md`, `docs/CODE-STANDARDS.md`
- **MVP** Design folder: `VISION`-style doc, living design doc and a dated decisions log
- **MVP** `docs/parallel-lanes.md` explaining the lane workflow

## 10. Stack packs (optional add-ons)
- **MVP** Unity pack: `.gitignore`/`.gitattributes`, `.mcp.json`, per-lane editor setup, reviewer items, rules-check patterns, test runner command, sibling-folder worktree notes
- **Later** Python pack, Node/web pack
- **MVP** Pack format documented so new packs are easy to add

## 11. Public showcase support
- **Later** `showcase export`: snapshot to a public repo, excluding a never-copy list, checking for secrets and placeholders first

## 12. Distribution
- **MVP** GitHub template repository ("Use this template")
- **Later** Claude Code plugin packaging
- **MVP** Semantic versioning and a changelog for the kit itself
- **MVP** MIT license

## 13. Documentation and presentation
- **MVP** README: what it is, 3-step quickstart, architecture diagram, guardrail table
- **MVP** Example Python project set up with the kit, showing a plan, a review report and a lane merge
- **Later** Demo GIF of `lanes create` → two agents working → `lanes merge`
- **Later** FAQ, troubleshooting, "why this design" page

## 14. Quality of the kit itself
- **MVP** pytest for the setup script and every hook, in CI on Windows and Ubuntu
- **MVP** Windows-first testing (paths with spaces, CRLF), then Mac/Linux
- **Later** Linting and formatting for the kit's own code

## Build order
1. ✅ Survey the Hall of Echoing Mirrors setup (`survey-hoem.md`)
2. Repo skeleton, CI, kit's own CLAUDE.md/AGENTS.md
3. Core instructions + skills + reviewer
4. Rules-check and protected-paths hooks with tests
5. Lane config + `lanes create/status` + lane-router hook
6. Setup script, then `lanes sync/merge`
7. Unity pack
8. README, example project, template repo, then plugin packaging
