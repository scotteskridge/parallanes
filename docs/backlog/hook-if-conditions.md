---
status: later
lane: any
size: S
---
# Spawn hooks only for the calls they check

A hook entry can carry an `if` field, such as `"if": "Bash(git *)"`, and the hook process only
starts when the tool call matches ([hooks](https://code.claude.com/docs/en/hooks.md)). Every kit
hook starts Python (about 35 ms or more on Windows per process); the protected backstop runs on
every Bash call and file edit. Narrowing which calls spawn it cuts that cost without changing what
it guards. Care needed: the backstop fails closed, so an `if` must never skip a call it should see.

**Done when:** the settings template and `kit settings sync` use `if` where it is provably safe,
with tests that the guarded cases still reach the hook.
