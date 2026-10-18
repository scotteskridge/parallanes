---
status: idea
lane: any
size: S
---
# Trust a merge's other side only when it has already landed

Pre-commit judges a merge commit on its resolution only (decisions 96 and 115), whatever
MERGE_HEAD points at. So a protected change or secret committed without the hook (`--no-verify`,
`git commit-tree`, a stash), then brought in by a merge that stops (`--no-commit`, a conflict),
passes locally; CI's `--diff` still catches it. Two ways to close it, for the owner's call: use
the resolution-only rule only when MERGE_HEAD is reachable from the integration branch (or its
remote), else judge the whole index; and/or install a `pre-merge-commit` hook, since a merge that
doesn't stop never runs pre-commit at all. A fast-forward runs no hook either way and stays CI's
job. An octopus merge also compares only with its first head (over-reports, fails closed).

**Done when:** the owner has decided, and a merge commit that brings in a commit which skipped the
hook is judged in full by the protected and lane-boundary checks, with a test.
