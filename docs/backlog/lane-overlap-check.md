---
status: next
lane: any
size: S
---
# Settle overlapping lanes when the config loads

`lanes status` already notes lanes that *may* overlap, judged by the literal folder each `owns`
glob starts from (`kitlib/lane_status.py`, `overlaps`). It's a hint: it can't tell whether a real
file is claimed twice, and nothing says which lane owns that file. [lanekeeper](https://github.com/kish21/parallel-agents)
settles it with a rule: the more specific pattern wins, the order in the file doesn't matter, and
an exact tie is a config error naming both lanes, because it means nobody has decided yet.

Reference: `docs/survey-lanekeeper.md` (the ranking rule).

**Done when:** owning a file is defined by a written rule (decision logged); `lanes create` and
`lanes status` list the tracked files more than one lane claims, with which lane wins; a tie is an
error at load; the ownership hook and the lane-boundary check use the same rule.
