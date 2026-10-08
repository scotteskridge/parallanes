---
status: later
lane: any
size: M
---
# Offer a "Use this template" starting point

ROADMAP listed a GitHub template repository for v0.1; decision 108 dropped it. Marking the kit's
own repo a template hands people its development repo, and a pre-installed blank project would
carry one machine's `python-path`. Worth doing if people ask for a one-click start: a small
template repo whose first step (a README line, or a SessionStart check) runs the installer to
record the local Python, and a CI job that keeps it in step with each release.

**Done when:** "Use this template" gives a project that passes `parallanes check all` after one
documented command, and the template is rebuilt from each release.
