---
status: next
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
