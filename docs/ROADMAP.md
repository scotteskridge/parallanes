# Roadmap

Goal: set up a new project with the full agent workflow (rules, skills, hooks, reviewer, parallel
lanes) in a few steps, instead of rebuilding it each time. Generalized from the Hall of Echoing Mirrors
setup (see `survey-hoem.md`). **MVP** = version 1; **Later** = after it's working.
Decisions behind this list: `decisions-log.md`. Design: `ARCHITECTURE.md`. Build sequence: `plans/README.md`.

## 1. Setup and installation
- **MVP** One-command setup: `install.ps1` (Windows first) and `install.sh` (Mac/Linux), both thin wrappers over one Python script
- **MVP** Asks only what it can't detect (project name, description, lanes, packs); `/onboard` fills the rest
- **MVP** Prerequisite check: git, Python 3.11+ (a real interpreter, not the Windows Store alias), Claude Code, gh (optional)
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
- **MVP** `/next`: lane-aware "what's next" (ready / waiting on you / blocked)
- **MVP** `/onboard`: after install, Claude reads the repo and proposes stack facts, test command, rules files and lanes for approval
- **Later** `/refactor`, `/sync-state` (keep status docs true), `/workflow` (maintain the kit itself)
- **Later** Role skills per lane (e.g., `/ui-work`, `/writing`) that load only that role's docs
- **MVP** Templates: plan file, decisions log entry, changelog entry, code-health report

## 4. Subagents
- **MVP** `reviewer`: fresh context, sees only the diff, the rules and the plan; numbered checklist; severity levels (fix now / fix soon / polish)
- **MVP** Reviewer checklist split into a universal part plus a stack-specific part (e.g., Unity items)
- **Later** Researcher/explorer subagent for codebase searches that would otherwise clutter the main session
- **Later** Test-writer subagent

## 5. Hooks (automatic enforcement)
- **MVP** Rules-check (PostToolUse on Edit/Write): forbidden patterns from `.claude/kit.toml` (pattern, glob, message); exits 2 so the agent fixes violations; fails open; ignores comments
- **MVP** Every check has three entry points: hook, CLI for humans and agents (`kit check ...`), and pre-commit; CI runs the CLI
- **MVP** Lane-router hook (SessionStart): tells the agent its lane, branch, scope, owned paths and resources; warns about drift
- **MVP** Protected paths: `settings.json` deny rules generated from config (primary) + PreToolUse command backstop (fails closed); README states the limits and recommends the sandbox where available
- **Later** Stop hook that reminds the agent to run tests if code changed without a test run
- **Later** Formatter/linter hook per stack
- **MVP** All hooks in Python, cross-platform, each with its own tests

## 6. Parallel lanes (the differentiator)
- **MVP** Lanes in `.claude/kit.toml`: name, scope, owned paths, resources (ports, editor instances); integration branch; merge mode
- **MVP** `lanes create`: branch and git worktree per lane (default `.claude/worktrees/<lane>/`), `.worktreeinclude` for local settings, optional shared auto-memory link
- **MVP** `lanes status`: each lane's branch, ahead/behind, uncommitted changes, unpushed work, PR state
- **MVP** `lanes start <task>`: short-lived task branch `<lane>/<task>` from the latest integration branch, after checking the previous one merged
- **MVP** `lanes sync`: brings the integration branch into the task branch (rebase if unpushed, merge if pushed)
- **MVP** `lanes finish`: tests → **PR mode** (default: push, open PR with the review report) or **local mode** (fast-forward the integration branch)
- **MVP** Ownership: out-of-lane edits become a permission prompt (configurable ask / warn / block / off)
- **MVP** Per-lane tool instances (e.g., separate Unity Editor + MCP port per lane)
- **Later** Lane handoff notes at session end
- **Later** Push-reminder for commits that exist only locally

## 7. Permissions and safety
- **MVP** `settings.json` template with allow/deny lists (root-anchored patterns, tested)
- **MVP** `.gitignore` / `.gitattributes` / `.worktreeinclude` templates (`settings.local.json`, caches, `.env`, LF endings)
- **MVP** Secrets guidance: keys live outside the repo; `.env` never committed
- **Later** Pre-commit secret scan

## 8. Verification and CI
- **MVP** Configurable test command, used by skills and the merge helper ("evidence, not claims")
- **MVP** GitHub Actions template for installed projects: tests and all checks on every push and PR
- **MVP** Evals: scenario tests that drive real `claude -p` sessions on the example project (on demand / nightly)
- **Later** Optional test-count and coverage report

## 9. Project documentation scaffolding
- **MVP** `docs/plans/` (+ `finished/`), `docs/CHANGELOG.md` built from `docs/changelog.d/` fragments, `docs/backlog/` (one file per item), `docs/BUILD-STATE.md`, `docs/CODE-STANDARDS.md`
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
The numbered plan series in [plans/README.md](plans/README.md), one PR per plan.
