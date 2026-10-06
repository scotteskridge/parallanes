# Survey: lanekeeper

A tool for the same problem as the kit: several AI coding agents on one repository without
collisions. Studied 2026-10-05 at [kish21/parallel-agents](https://github.com/kish21/parallel-agents)
v0.9.0, commit `2fdb7b2` (2026-09-07). MIT licensed, Python, one dependency (`pyyaml`).

> **Reference, not spec** (decisions 10, 74). We build on what it does well instead of reinventing
> it, and improve on it where the kit's design is different. Read the current source before
> borrowing; paths below are at the commit above. **Borrowed code keeps lanekeeper's MIT notice**
> (`Copyright (c) 2026 Lanekeeper Contributors`) and names the source file and commit in the
> borrowing file's docstring.

## How it differs from the kit

| | lanekeeper | the kit (`worklanes`) |
| --- | --- | --- |
| A lane is | a ticket's file list; one agent per lane, short-lived | a long-lived area or role; tasks cycle through it |
| Enforced | at merge: CI check on a `lane:` PR label, optional pre-push hook; fails closed | at the edit, inside Claude Code: ownership hook (fails open), protected paths (fails closed), rules check |
| Agent | any (vendor-neutral adapters) | Claude Code: hooks, skills, reviewer subagent |
| Landing | `pr`: check, push, labelled PR | `lanes finish`: sync, test the exact commit that lands, then PR or fast-forward |
| Resources | port pools with a ledger, `.env` per worktree, per-agent databases | `resources` values the lane-router reports |
| Size | ~13,500 lines of source (`cli.py` alone 2,680), ~12,700 of tests | ~3,500 of source (largest file 321), ~5,100 of tests |

Positioning: **lanekeeper stops the merge; the kit stops the edit and runs the whole task loop.**
The two could even be used together.

## What to borrow, by future step

Each row: what it does, where it is, and how the kit would take it.

| For | lanekeeper source | Take | Adapt for the kit |
| --- | --- | --- | --- |
| `lane-boundary-check` | `src/lanekeeper/check.py` (`check_checkout`, `github_summary`, `annotations`, `workflow_text`) | The check's rules: a rename is a change to both paths; a diff that can't be computed fails ("nothing was checked"); policy files belong to no lane; the lane comes from a label *or* the branch name, and a disagreement fails | Lane from the `<lane>/<task>` branch name; one more `kit check` target, so it gets CLI, pre-commit and CI for free |
| `lane-boundary-check` | `tests/test_gate_holes.py`, `test_changed_files.py`, `test_lane_fail_closed.py` | **The test list** (below): bypasses they found the hard way | Port the cases, not the code |
| `ci-check-annotations` | `check.py` `github_summary`, `annotations` | Verdict as markdown in `$GITHUB_STEP_SUMMARY`; `::error file=…::` lines so each violation shows on the PR's Files tab; escape `%`, `\r`, `\n` | For every `kit check`, behind a `--github` flag; plan 09's CI template turns it on |
| `lane-overlap-check` | `src/lanekeeper/lanes.py`, README "The four rules that decide who owns a path" | Shared zones first; between lanes the most specific pattern wins (most wildcard-free segments, then length); file order never matters; an exact tie is a load error | The kit's globs and `kitlib/globs.py` stay; only the ranking rule is new |
| `shared-path-modes` | README "The shared middle", "`shared` needs a steward", "`append_only`" | `escalate` / `append_only` modes and a steward lane | Map onto `shared_paths`; the kit's own shared docs are append-only by nature |
| `lane-resources-env` | `src/lanekeeper/ports.py`, `environment.py`, `frameworks.py` | The socket probe (`connect_ex` on 127.0.0.1, short timeout); URL templates (`VITE_API_URL: http://${HOST}:${BACKEND_PORT}`); **the client-env-prefix table** (`vite`→`VITE_`, `next`→`NEXT_PUBLIC_`, `react-scripts`→`REACT_APP_`, `nuxt`, SvelteKit, Gatsby, Expo, Remix, Astro, Angular) read from `package.json` dependencies | **Improve:** kit lanes are long-lived, so ports can be fixed per lane in `kit.toml` (or lane index × stride). No ledger, no lock, no orphaned reservations; only the probe, as a warning |
| `lane-dependency-hint` | `src/lanekeeper/deps.py` | **The lockfile table:** `pnpm-lock.yaml`→`pnpm install --frozen-lockfile`, `yarn.lock`→`yarn install --immutable`, `package-lock.json`→`npm ci`, `uv.lock`→`uv sync`, `poetry.lock`→`poetry install`, `Pipfile.lock`→`pipenv sync`, `Gemfile.lock`→`bundle install`, `composer.lock`→`composer install`; a manifest without a lockfile says the install is the owner's call; no manifest says nothing | `lanes create` prints the line for each new worktree; `/onboard` (07b) can suggest it as a lane setup step |
| `ownership-fix-hint` | `lanekeeper allow` (README CLI table) | One command that widens a lane on purpose and refuses another lane's path, a shared zone or the policy | A suggested `kit.toml` line in the hook's prompt first; a command only if needed |
| `doctor-and-uninstall` | `src/lanekeeper/doctor.py`, `uninit.py`, `tests/test_cleanup_honesty.py` | Problem classes (orphaned, conflict, stale); uninstall shows a plan, asks, never deletes an unmerged branch, names what it kept; a failed cleanup stays visible to `doctor` | Kit-owned vs project-owned (decision 7) decides what uninstall may remove |
| Plan 08 (installer) | `src/lanekeeper/codeowners.py` (`BEGIN`/`END` markers) | **Managed blocks** in files the user owns (`.gitignore`, CODEOWNERS): only the text between markers is rewritten; a lone or doubled marker is an error, never repaired silently | How the installer edits `.gitignore` and `.gitattributes` without overwriting them |
| `codeowners-from-lanes` | `codeowners.py`, `docs/codeowners.md` | Write `.github/CODEOWNERS` from lanes inside managed markers; CODEOWNERS takes the *last* match, so write lanes → shared → policy; `--check` fails on drift | Optional: routes PR reviews by lane on GitHub with nothing else installed |
| Messages and Windows | `src/lanekeeper/invocation.py`, `__main__.py`, README Windows section | "Run this next" lines repeat the command the way the person started it (`python -m …` when the shim isn't on PATH); an env override for wrappers | The kit runs as `sh .claude/kit/kit` (plan 07); check its messages name that form |
| Plan 12 (docs) | `docs/why-lanekeeper.md`, `docs/getting-started.md`, README "What it does not do" | A story-first "why" page; getting started with real output; an honest "does not do" list; a Windows PATH section | Same shape for `worklanes`, with the Claude Code built-ins table |
| Process | test files named `test_*_findings.py` (`new_user`, `first_run`, `trial`, `deep_test`) | Each trial run with a new user becomes a test file of its findings | Fits `prove-it-on-a-real-project` and plan 11's evals |

## Test cases to port for the lane-boundary check

From `tests/test_gate_holes.py`, `test_changed_files.py` and `test_lane_fail_closed.py`:

- a move out of another lane is a violation, committed or not; so is a move of a denied file
- a missing base branch is an error, never a clean result
- widening the lane policy inside a lane's own change is a violation, even for a lane that allows everything
- a trailing slash in a pattern means everything under it, in allow and deny alike
- an empty, missing or null allow list is refused at load; a single string isn't split into letters
- creating, modifying and deleting a protected file are all blocked
- paths with spaces and non-ASCII names survive `git status` parsing; a rename reports both paths
- an undeclared lane is refused with nothing provisioned; there is no permissive fallback

## Not to copy

- **The scope:** ticket intake, work division with an AI advisor, seats and capability cards, a
  GitHub project board, and coupling to the author's other tool. Each is a product of its own.
- **The weight:** a 2,680-line `cli.py` and an 800-line `CLAUDE.md`. The kit's ~300-line file limit and
  short instructions are worth keeping.
- **Lane per ticket:** it needs every ticket to list its files, which lanekeeper calls its one real
  prerequisite. The kit's long-lived lanes fit persistent resources (an editor instance per lane)
  and don't need that.
- **A port ledger and lock:** needed for short-lived agents, not for long-lived lanes (see above).
- **`pyyaml`:** the kit stays standard-library only; `kit.toml` uses `tomllib`.
