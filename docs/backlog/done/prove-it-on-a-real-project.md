---
status: now
lane: any
size: M
---
# Prove the lanes on a real non-Unity project

The kit's code is stack-agnostic, but only its author has used it, and on one kind of project.
The real-world problem it claims to solve is parallel agents colliding on one repo: files, branches
and shared resources such as dev-server ports, databases or emulators. Run two lanes on a small
web project, each with its own dev-server port, through a few real tasks each, and keep notes on
what saved time and what got in the way. That's both the usefulness test and the showcase story.
A rough version of plan 11's example project, done earlier.

Also count what the kit caught that plain worktrees wouldn't have (decision 98): edits outside a
lane's paths that the hook stopped to ask about, cross-lane changes that `kit check lanes` or
`lanes finish` refused, ties between lanes flagged, and conflicts surfaced by syncing and testing
the exact commit before it lands. Those real cases are the README's answer to "why not Claude
Code's own worktrees?"

**Done when:** at least three tasks per lane went through `lanes start` → work → `lanes finish`,
a short write-up lists the friction found (each becoming a backlog item or a cut) and what the
kit caught, and the README can show a real two-lane run.

**Outcome (2026-10-07):** done, except as noted below. Six tasks, three per lane, on a
reading-list app, with a write-up of what the kit caught and the friction found:
[docs/trial/two-lane-trial.md](../../trial/two-lane-trial.md).

**Decided (decision 103): the trial repo is published at launch.** "The README can show a real
two-lane run" is met only in that the material now exists. ROADMAP's MVP line wants the run in the README "with its plan, review report and lane
merges", but the trial repo is local only (`D:\1 office\worklanes-trial`). Recommendation: publish
it at launch (plan 12, with `readme-builtins-comparison`) and link its commits, plans and review
reports from the write-up and the README.
Friction became `installer-dry-run-prompts`, `local-mode-setup-hints`, `decision-log-fragments` and
`lane-guide-trial-notes`, and extended `lane-dependency-hint`, `ownership-fix-hint` and
`lane-resources-env`. Build order step 5's companions (`lanes-and-worktree-flag`,
`lane-dependency-hint`) are still open.
