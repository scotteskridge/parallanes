---
status: idea
lane: any
size: M
---
# Make code comments that cite decisions readable on their own

About 60 comments cite a decision number alone ("decision 33"). It keeps them traceable, but a
reader needs `docs/decisions-log.md` open to follow the code. A short reason with the number
("fails closed: in PreToolUse only exit 2 blocks (decision 33)") works both ways.

**Done when:** every comment that cites a decision also says the reason in a few words, and
`CODE-STANDARDS` or AGENTS.md states the convention.
