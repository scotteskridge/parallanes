---
status: later
lane: any
size: L
---
# Make lane resources real: ports in each lane's environment

A lane's `resources` are free-form values the lane-router only *tells* the agent about
(`kitlib/lane_hooks.py`). For a web project that isn't enough: a dev server still starts on its
default port, and a frontend built with Vite or Next.js only sees `VITE_*` / `NEXT_PUBLIC_*`
variables, so it talks to whichever backend its source names, usually another lane's.
[lanekeeper](https://github.com/kish21/parallel-agents) allocates ports per agent, checks the host
that they're free, writes them into the worktree's `.env`, and generates URL variables from
templates (`VITE_API_URL: http://${HOST}:${BACKEND_PORT}`).

This is the change most likely to make the kit useful beyond Unity; pair it with
[prove-it-on-a-real-project](done/prove-it-on-a-real-project.md) (done:
[the write-up](../trial/two-lane-trial.md)). Open for the owner: which file the kit writes (a
lane-local `.env` it owns, or a block inside the project's), and whether it stays stdlib-only (it
can).

Reference: `docs/survey-lanekeeper.md` (the port probe, URL templates and the client-env-prefix
table). Improve on it: long-lived lanes can have fixed ports per lane, so the kit needs no ledger or
lock, only the probe as a warning.

**From the two-lane trial:** being *told* the port was enough for a plain Express app that reads
`PORT` (agents and the owner ran `PORT=3002 npm start`); the env-file work matters once a frontend
build or a second service needs the values.

**Done when:** a lane's ports come from `kit.toml` (or a range), `lanes create` writes them and the
URL variables into the lane's environment file, `lanes status` warns when one is already taken,
and a two-lane web project runs both dev servers at once without editing any config by hand.
