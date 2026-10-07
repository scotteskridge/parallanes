---
status: next
lane: any
size: S
---
# Fix three things the trial found in the lane guide

From the two-lane trial:
- **F5:** a task takes two prompts: the work, then `/wrap-up`. The payload skills are
  `disable-model-invocation`, so "finish it with /wrap-up" inside a prompt makes the agent stop and
  ask. `docs/ai/parallel-lanes.md` should say so.
- **F6:** `web` owned only `public/**`, so its agent put tests in `public/`, where Express serves
  them. The `kit.toml` comment should say to give a lane its tests' folder too when code and tests
  don't share one.
- **F7:** an agent in a lane tried to read the main checkout's `.claude/skills/implement/SKILL.md`,
  and Claude Code refused (outside the working folder). Find out whether the skill listing points at
  the main checkout's copy, and document it or work around it.

**Done when:** the guide and the template carry the first two, and F7's cause is recorded in
ARCHITECTURE §15 with a fix or a note.
