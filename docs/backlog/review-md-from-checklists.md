---
status: idea
lane: any
size: S
---
# Generate REVIEW.md from the review checklists

Claude Code's managed Code Review (Team/Enterprise) reads `CLAUDE.md` and a root `REVIEW.md` for
review-only rules ([code-review](https://code.claude.com/docs/en/code-review.md)). The kit's
checklists already live in `.claude/review/`. Writing `REVIEW.md` from them would let one source
serve both the kit's reviewer and Code Review. Local `/code-review` doesn't read `REVIEW.md`.

**Done when:** the owner decides it's worth it; if so, a kit command writes `REVIEW.md` inside
managed markers (see `docs/survey-lanekeeper.md`, plan 08 row) and a check fails on drift.
