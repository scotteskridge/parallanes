---
status: next
lane: any
size: S
---
# Say how to install dependencies in a new lane

A worktree is a fresh checkout: no `node_modules`, no virtualenv. The first thing an agent does in
a new lane fails, and nothing says why. lanekeeper reads the lockfile to name the install command
(`npm ci`, `pnpm install --frozen-lockfile`, `uv sync`, ...), and says it's the owner's call when
there's a manifest but no lockfile. Table and rules: `docs/survey-lanekeeper.md`, row
`lane-dependency-hint`.

**Worse in practice (two-lane trial, F4):** nothing failed at all. Lanes in `.claude/worktrees/`
sit inside the main checkout, and Node resolves packages up the folder tree, so every lane silently
ran the main checkout's `node_modules`. A lane that changes a dependency would test the old version
and see green. Python's venv and other tools that search parent folders can do the same. So the
hint should say *why* to install in each lane, and `lanes status` (or the lane-router) should warn
when a lane has a manifest but no install of its own.

**Done when:** `lanes create` ends each new lane's lines with the install command for that project
(or "your call", or nothing when there's no manifest), with tests for each lockfile, a manifest
without one, and none.

**Outcome:** decision 103. `kitlib/lane_deps.py` holds the table (plus Bun's lockfiles). `lanes
create` prints an install line under each new lane and says why once; `lanes status` and the
lane-router warn when a lane has `package.json` but no `node_modules`. Only Node is warned about,
and only the lane's root is read.
