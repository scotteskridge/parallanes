---
status: idea
lane: any
size: S
---
# Leave the optional skills out of the solo profile

Every installed skill's description is loaded into each session's context, so `/design` and
`/code-health`, which most solo users won't run, cost a few hundred tokens a session. Plan 16's
solo profile leaves out two hooks but still installs every skill. Measure what the descriptions
cost first; then decide whether solo skips them or asks.

**Done when:** a solo install's per-session instruction cost is measured, and the optional skills
are left out or kept with the number written down.
