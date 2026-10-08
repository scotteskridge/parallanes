---
status: idea
lane: any
size: S
---
# Keep plan revisions on Opus

`/plan-feature` runs on Opus through its `model:` line, but Claude Code applies a skill's model
only to the turn the skill runs in. When the owner answers the plan's questions or pushes back, the
revision happens in the next turn, on the session's model (often Sonnet). That is where the
owner's judgement and the planner's matter most. Hooks can't fix this: no hook event can choose a
model (`PreModelSwitch` can only allow or block a switch the user asked for). Checked against
code.claude.com/docs/en/skills.md and hooks.md on 2026-10-08.

Likely shape: `/plan-feature docs/plans/<plan>.md` revises an existing plan with the owner's
answers, so each revision is a new skill turn on Opus. Step 5 then ends with "to revise, run
`/plan-feature <this plan>` with your answers" instead of handling the answers in the same chat.
The approval turn (set Approved, write the decisions-log entry) also runs on the session's model
today. A revision run must skip step 3 (it already has its task branch) and accept its own draft
plan as the folder's only change, which step 0 currently refuses. Until then, the README tells
owners to switch with `/model opus` first.

**Done when:** answering or pushing back on a plan has a documented path that runs on the
planning model, with a test that the skill accepts an existing plan's path, and a live check
that the revision turn ran on Opus.
