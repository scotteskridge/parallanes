---
status: next
lane: any
size: M
---
# Stop lanes colliding on the decisions log

Every lane adds its decisions at the top of `docs/design/decisions-log.md`, a shared path, so two
lanes that both decide something conflict on the same lines. In the two-lane trial (F12) it
happened on the third round: `lanes finish` surfaced it while syncing and the agent merged the
entries by hand, which works but costs a step and a judgement call every time. The changelog
already avoids this with one fragment file per change (`docs/changelog.d/`).

Open for the owner: decision fragments gathered by a `kit` command (like `changelog build`), or a
merge rule (`merge=union` in `.gitattributes`) that keeps both sides of a top-of-file insert.

**Done when:** two lanes that each log a decision both land without a conflict, with a test that
runs that case.
