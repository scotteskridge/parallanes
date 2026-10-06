---
status: idea
lane: any
size: M
blocked_by: lane-overlap-check
---
# Generate CODEOWNERS from the lanes

Lanes and GitHub's `CODEOWNERS` hold the same facts: which paths belong to whom. Writing one from
the other makes the lanes route PR reviews on GitHub with nothing installed, and readable to people
who've never heard of the kit. lanekeeper does it inside managed markers, in an order that matches
GitHub's last-match-wins rule, with a `--check` that fails on drift. Details:
`docs/survey-lanekeeper.md`, row `codeowners-from-lanes`. Only useful with an `owner` per lane,
which `kit.toml` doesn't have yet: an owner's call.

**Done when:** the owner has decided whether lanes get owners; if yes, a kit command writes the
managed block, keeps everything outside it, and a check mode fails on drift.
