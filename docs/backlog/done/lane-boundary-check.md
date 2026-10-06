---
status: next
lane: any
size: M
---
# Check lane ownership when work lands, not only while editing

Lane ownership is enforced only by the `ownership` hook, which asks before an out-of-lane edit
and deliberately fails open (decision 41). Nothing backs it up: a change made outside Claude Code,
with ownership `off`, or after a "yes" in the prompt lands without anyone checking it.
[lanekeeper](https://github.com/kish21/parallel-agents) enforces the same idea at merge (a
CI check and a pre-push hook) and fails closed. Defence in depth: the hook guides the agent, the
check guarantees the result.

Add a `lanes` check to `kit check` with the usual three entry points (CLI, pre-commit, CI, as ROADMAP §5
asks of every check), and run it in `kit lanes finish` before anything lands. Worth taking from lanekeeper:
a rename counts as a change to the old path too; a diff that can't be computed fails the check
rather than passing; the kit's own policy files belong to no lane. Open for the owner: how CI knows
the lane (from the `<lane>/<task>` branch name seems natural) and what a deliberate cross-lane
change looks like (a label, a trailer, or an owner-only path).

Reference: `docs/survey-lanekeeper.md` (the check's rules, and the test cases to port).

**Done when:** `kit check lanes --diff origin/main` fails a change touching another lane's files or
an unowned path, names each file, and passes shared paths; `lanes finish` refuses such a change; tests
cover renames, deletions, shared paths and a missing base.

Done 2026-10-06: decision 96. `kit check lanes` (in `check all`) and `kit lanes finish` refuse a lane change outside its paths; tests in `tests/test_lane_boundary.py` and `tests/test_lane_finish.py`.
