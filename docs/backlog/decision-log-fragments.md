---
status: next
lane: any
size: M
---
# Keep the decisions log in order across lanes

ARCHITECTURE §8 keeps `docs/design/decisions-log.md` as one newest-first file "for readability",
with the rule that a lane adds at most one entry per task. Decision 13 made the changelog fragments
instead and rejected `merge=union` as fragile; decision 72 made the log a default shared path. The
two-lane trial (F12, C4) tested §8's choice: both lanes prepended to the log, `lanes finish`
surfaced the conflict while syncing, and the agent's hand merge kept every entry but put the newest
one third, breaking newest-first. One task (`web/read-toggle`) had also added two entries, against
the one-entry rule, because nothing checks it.

Open for the owner, each reversing or tightening a settled choice:
- **(a) Fragments, like the changelog.** This reverses §8's readability choice; a `kit` command
  could build the readable log.
- **(b) `merge=union` for this one file.** This reverses decision 13 for it; it would need a
  reason that it's safe here when it wasn't for the changelog.
- **(c) Keep one file, and enforce §8.** `/wrap-up` checks for one entry per task and tells the
  agent how to merge a top-of-file conflict, keeping newest first.

Recommendation: (c). It keeps the decision already made, the trial's conflict was small, and the
real failures were the unchecked rule and the merge order.

**Done when:** the owner's choice is recorded in `docs/decisions-log.md`, and two lanes that each
log a decision land with the log still newest first, with a test for that case.
