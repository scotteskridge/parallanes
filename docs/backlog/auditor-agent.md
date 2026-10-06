---
status: idea
lane: any
size: S
---
# Give `/code-health` a read-only auditor agent

`/code-health` runs its area audits as Claude Code's built-in `Explore` agent with model `sonnet`.
`Explore` can't Edit or Write, but it has Bash, so "never run anything that writes" (tests,
coverage, formatters) rests on the prompt. A kit-owned `auditor` agent beside `reviewer.md`, with
`tools: Read, Grep, Glob` and `model: sonnet`, would be read-only by its tool grants and pin its
model in its definition. Cost: one more kit file. Plan 07b review round 2; the owner chose to wait
until a write is seen or the plugin route (plan 08) settles where agents live.

**Done when:** `/code-health` names `subagent_type: auditor`, the agent's tools are read-only (a
test like `test_reviewer_is_read_only`), and a live audit shows it reads files whole.
