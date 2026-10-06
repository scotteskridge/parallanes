---
status: next
lane: any
size: S
---
# Make every live check and eval say what it loads

`--bare` "will become the default for `-p` in a future release", and it skips hooks, skills,
subagents, plugins and `CLAUDE.md` ([headless](https://code.claude.com/docs/en/headless.md)). The
kit's live checks (plans 04–07) and plan 11's evals run `claude -p`; when the default flips they
would silently stop testing the kit. Agent frontmatter hooks are also skipped until the folder is
trusted. See `docs/survey-claude-code.md`, Plan 11.

**Done when:** every scripted `claude -p` run in the repo's docs, tests and plans passes explicit
flags for what it needs, trusts its scratch folder when it needs the reviewer's guard, and asserts
from the `system/init` stream event that the hooks, skills and plugins it relies on loaded.
