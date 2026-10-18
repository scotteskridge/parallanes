---
status: idea
lane: any
size: S
---
# Judge a merge commit's rules on its resolution only

During `git merge --continue`, `parallanes check rules --staged` reads every file the index
changes against HEAD, so a file the integration branch changed is checked again as this commit's
change, and a rule it breaks there blocks the merge. The protected and lane-boundary checks take
only the resolution (`gitfiles.touched_by_merge_commit`, decisions 96 and 115); left out of
`protected-check-merge-commits` to keep it narrow. Open question: a merge that leaves main's broken
file in place arguably should still fail, since the commit carries it.

**Done when:** the owner has decided, and if so, with MERGE_HEAD present the rules check reads only
the files that differ from both parents, with a test.
