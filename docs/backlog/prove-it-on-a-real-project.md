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

**Done when:** at least three tasks per lane went through `lanes start` → work → `lanes finish`,
a short write-up lists the friction found (each becoming a backlog item or a cut), and the README
can show a real two-lane run.
