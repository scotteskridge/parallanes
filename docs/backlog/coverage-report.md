---
status: later
lane: any
size: S
---
# Report test coverage in CI

The suite is strong (about 5,100 lines of tests for 3,500 of source), but nothing shows how much
of the code it reaches. A coverage number is cheap and readers expect it. `.coverage` and
`htmlcov/` are already gitignored. ROADMAP §8 lists a coverage report as Later for installed
projects; this item is the kit's own.

**Done when:** CI prints a coverage summary for `payload/kit-owned/.claude/kit/` on the full-suite
jobs (pytest-cov, dev-only). No minimum to start with.
