---
status: idea
lane: any
size: S
---
# Name the main checkout's branch even before its first commit

`lanes.branch_of` uses `git rev-parse --abbrev-ref HEAD`, which fails on an unborn branch (say,
after `git checkout --orphan`) and can print `heads/<name>` when a tag shares the name. So
`lanes status`, the lanes part of `parallanes next`, and `lanes create` in local mode stop with
git's raw error while the main checkout is on an unborn branch. `gitfiles.current_branch` already
reads the branch with `symbolic-ref`, which works there. Found in `local-mode-setup-hints` review
round 2; left out to keep that change narrow.

**Done when:** those commands work with the main checkout on an unborn branch (tested), and every
`branch_of` caller (`lane_cycle`, `lane_hooks`, `lane_status`, `lane_setup`) still behaves the same
on a normal one.
