# Roadmap

Goal: set up a new project with the full agent workflow (rules, skills, hooks, reviewer, parallel
lanes) in a few steps, instead of rebuilding it each time. Generalized from the Hall of Echoing Mirrors
setup (see `survey-hoem.md`). **MVP** = v0.1, the first release; **v0.2** = the next one; **Later** = after that.
What v0.1 holds and the order it's built in: decision 77 and [plans/README.md](plans/README.md).
Decisions behind this list: `decisions-log.md`. Design: `ARCHITECTURE.md`. Build sequence: `plans/README.md`.

## 1. Setup and installation
- **MVP** One-command setup: `install.ps1` (Windows first) and `install.sh` (Mac/Linux), both thin wrappers over one Python script
- **MVP** Asks only what it can't detect (project name, description, stack, test command, integration branch, pre-commit), each with a detected default; `/onboard` (v0.2) fills the rest. Lanes are added to `kit.toml` afterwards (decision 101)
- **MVP** Prerequisite check: git, Python 3.11+ (a real interpreter, not the Windows Store alias), Claude Code, gh (optional)
- **MVP** Works on a brand-new folder *or* an existing repo, without overwriting existing files: the kit's version goes beside yours as `.kit-new`, and a re-run is safe (decision 100)
- **MVP** Dry-run mode that lists what it would create before doing anything. *Done in plan 08* (with the four lines above).
- **Later** Non-interactive mode (answers from a config file) for repeat setups
- **v0.2** Updates through the Claude Code plugin marketplace (decision 78), instead of a copy-based update command
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
- **v0.2** `/onboard`: after install, Claude reads the repo and proposes stack facts, test command, rules files and lanes for approval
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
- **MVP** Protected paths: `settings.json` deny rules generated from config (primary) + PreToolUse command backstop (fails closed); each project's `docs/ai/protected-paths.md` states the limits and recommends the sandbox where available
- **Later** Stop hook that reminds the agent to run tests if code changed without a test run
- **Later** Formatter/linter hook per stack
- **MVP** All hooks in Python, cross-platform, each with its own tests

## 6. Parallel lanes (the differentiator)
- **MVP** Lanes in `.claude/kit.toml`: name, scope, owned paths, resources (ports, editor instances); integration branch; merge mode
- **MVP** `lanes create`: a git worktree per lane (default `.claude/worktrees/<lane>/`), detached at the integration branch between tasks; `.worktreeinclude` for local settings
- **MVP** `lanes status`: each lane's branch, ahead/behind, uncommitted changes, unpushed work, PR state
- **MVP** `lanes remove`: deletes a lane's worktree; refuses uncommitted changes and ignored files that may hold work
- **MVP** `lanes start <task>`: short-lived task branch `<lane>/<task>` from the latest integration branch, after checking the previous one merged
- **MVP** `lanes sync`: brings the integration branch into the task branch (rebase if unpushed, merge if pushed)
- **MVP** `lanes finish`: tests → **PR mode** (default: push, open PR with the review report) or **local mode** (fast-forward the integration branch)
- **MVP** Ownership: out-of-lane edits (including the main checkout and other lanes' folders) become a permission prompt (`ask`, or `off`)
- **MVP** Each lane's `resources` (ports, editor instances) reported to its agent
- **v0.2** Per-lane ports written into each lane's environment (backlog `lane-resources-env`, `lane-session-identity`); per-lane Unity Editor setup comes with the Unity pack
- **Later** Lane handoff notes at session end
- **Later** Lane-aware memory: Claude Code's auto memory is shared by every lane of a repo (plan 04's live check), so lane-specific notes need their own place
- **Later** Push-reminder for commits that exist only locally

## 7. Permissions and safety
- **MVP** `settings.json` template with allow/deny lists (root-anchored patterns, tested)
- **MVP** `.gitignore` / `.gitattributes` / `.worktreeinclude` templates (`settings.local.json`, caches, `.env`, LF endings)
- **MVP** Secrets guidance: keys live outside the repo; `.env` never committed
- **Later** Pre-commit secret scan

## 8. Verification and CI
- **MVP** Configurable test command, used by skills and `lanes finish` ("evidence, not claims")
- **MVP** GitHub Actions template for installed projects: tests and all checks on every push and PR. *Done in plan 09.*
- **v0.2** Evals (about five, decision 80): scenario tests that drive real `claude -p` sessions on the trial project (on demand / nightly)
- **Later** Optional test-count and coverage report

## 9. Project documentation scaffolding
- **MVP** `docs/plans/` (+ `finished/`), `docs/CHANGELOG.md` built from `docs/changelog.d/` fragments, `docs/backlog/` (one file per item), `docs/CODE-STANDARDS.md`
- **Later** `docs/BUILD-STATE.md`, together with `/sync-state` that keeps it true
- **MVP** Design folder: a dated decisions log, plus optional `VISION.md` and `DESIGN.md` stubs
- **MVP** `docs/ai/parallel-lanes.md` explaining the lane workflow

## 10. Stack packs (optional add-ons)
- **v0.2** Unity pack: `.gitignore`/`.gitattributes`, `.mcp.json`, per-lane editor setup, reviewer items, rules-check patterns, test runner command, sibling-folder worktree notes
- **Later** Python pack, Node/web pack
- **v0.2** Pack format documented so new packs are easy to add

## 11. Public showcase support
- **Later** `showcase export`: snapshot to a public repo, excluding a never-copy list, checking for secrets and placeholders first

## 12. Distribution
- **Later** GitHub template repository ("Use this template"): dropped from v0.1 (decision 108, backlog `template-repo`)
- **v0.2** Claude Code plugin packaging, named `worklanes` (decisions 73, 78)
- **MVP** Semantic versioning and a changelog for the kit itself
- **MVP** MIT license

## 13. Documentation and presentation
- **MVP** README: what it is, 3-step quickstart, architecture diagram, guardrail table
- **MVP** A real two-lane trial on a small web project, shown in the README with its plan, review report and lane merges (decision 80)
- **Later** Demo GIF of `lanes create` → two agents working → `lanes finish`
- **Later** FAQ, troubleshooting, "why this design" page

## 14. Quality of the kit itself
- **MVP** pytest for the setup script and every hook, in CI on Windows and Ubuntu
- **MVP** Windows-first testing (paths with spaces, CRLF), then Mac/Linux
- **MVP** Fast test feedback for building the kit. The suite takes ~2 min locally and ~5 min in CI
  (667 tests, measured after plan 05). The ~250 lane tests take 85% of the time, at 3–5 s each,
  because each builds a fresh repo, bare origin and worktrees and runs the CLI as a subprocess. CI
  ran the same suite in 41 s on Ubuntu and ~5 min on Windows, so the cost is mostly process starts
  on Windows: cut the number of git and Python processes. Ideas:
  - build each fixture repo once per session and copy it;
  - call the CLI in-process where the test isn't about the process boundary;
  - a `slow` marker, so sessions run the fast set by default and the full set before a commit or PR;
  - CI runs the full set on one OS/Python and the fast set on the others.

  Target: the default local run in under 20 s. *Done in `chore/fast-tests`:*
  - the fast set (488 tests, `-m "not slow"`) runs in 14–16 s, with unit tests on canned git and gh output covering every lane module;
  - the full suite went from 135–155 s to 80–107 s (timings on this machine vary a lot), by building fixture repos once per worker, cutting
    git calls and turning off git's auto-maintenance in tests;
  - CI runs the full suite once per OS.

  What's left is mostly the CLI process each lane test starts, kept because the process boundary is
  part of what they test.
- **MVP** Linting and formatting for the kit's own code (backlog `lint-and-format-in-ci`). *Done:* `ruff check` and
  `ruff format --check` run in CI's `lint` job, line length 120 (decision 94).

## Build order
The numbered plan series in [plans/README.md](plans/README.md), one PR per plan.
