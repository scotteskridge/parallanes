---
status: next
lane: any
size: M
---
# Close the gaps an outside review found before going public

An outside review (2026-10-06) judged the kit a strong showcase of engineering process but an
unproven tool: only its author has used it, and the README doesn't yet answer "why not Claude
Code's own worktrees, or lanekeeper?" Checking the current docs showed persistence isn't the
answer (Claude Code reuses named worktrees); enforcement is: owned paths, out-of-lane edits
stopped to ask, cross-lane changes refused, and the task cycle (decision 98).

What the review asked for, and where each point went:

1. **A real trial before going public.** Already `prove-it-on-a-real-project` (build order step 5).
2. **Show the win with real evidence.** Folded into `prove-it-on-a-real-project`: it records what
   the kit caught that plain worktrees wouldn't have.
3. **The "Claude Code does / the kit adds" table, with one honest line on lanekeeper.** Already
   `readme-builtins-comparison` (plan 12).
4. **Move the Unity pack (plan 10) ahead of generic polish.** Declined (decision 98): plan 10
   stays v0.2.
5. **The process can read as over-engineered.** Folded into `readme-builtins-comparison`: the
   README carries a reader in about two minutes; the process docs stay as depth.
6. **Set a ship date.** Declined (decision 98): no fixed date.

**Done when:** each point above is either done, folded into an existing item or plan, or cut with a
line in `docs/decisions-log.md`, and this file moves to `done/`.
