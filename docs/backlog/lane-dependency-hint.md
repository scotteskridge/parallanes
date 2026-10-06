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

**Done when:** `lanes create` ends each new lane's lines with the install command for that project
(or "your call", or nothing when there's no manifest), with tests for each lockfile, a manifest
without one, and none.
