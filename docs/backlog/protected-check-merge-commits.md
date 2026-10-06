---
status: next
lane: any
size: S
---
# Judge a merge commit's protected paths on its resolution only

During `git merge --continue` (which `lanes sync` asks for after a conflict on a pushed branch),
`kit check protected --staged` diffs the index against HEAD, so a protected path that changed on
the integration branch is reported as this commit's change and the pre-commit hook blocks the merge.
The lane-boundary check already avoids this with `gitfiles.touched_by_merge_commit` (decision 96);
found by its review, left out to keep that change narrow.

**Done when:** with MERGE_HEAD present, the protected check takes only the paths that differ from
both parents, and a test resolves a conflict with a protected change from main without a finding.
