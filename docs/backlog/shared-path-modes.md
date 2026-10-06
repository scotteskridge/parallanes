---
status: later
lane: any
size: M
blocked_by: lane-boundary-check
---
# Give shared paths a mode: append-only or ask

`shared_paths` today means any lane may change those files freely. Most of them only ever gain
files: changelog fragments, backlog items, plans, migrations. [lanekeeper](https://github.com/kish21/parallel-agents)
splits shared zones into `append_only` (adding a file is free, editing an existing one needs a
person) and `escalate` (any change needs a person), with an optional **steward**: the one lane
that may edit the zone directly (e.g. a platform lane owning the app's entry file).

That fits the kit's own shared docs exactly, and stops one lane rewriting another's fragment or
an applied migration. Open for the owner: the `kit.toml` shape, and whether the default shared
paths become `append_only`.

Reference: `docs/survey-lanekeeper.md`.

**Done when:** a shared path can be marked append-only or ask, with an optional steward lane; the
ownership hook and the lane-boundary check both honour it; the default shared paths have a
recorded mode.
