---
name: next
description: "Say where the kit's build stands and what to do next: branch and uncommitted work, open PRs and CI, plans waiting on the owner, the next plan to start, and docs that disagree. Read-only; ends with one recommended prompt. Use for /next, \"what's next\", \"where are we\"."
model: sonnet
effort: low
allowed-tools: Bash(git status *) Bash(git branch *) Bash(git log *) Bash(git rev-parse *) Bash(gh pr list *) Bash(gh pr checks *) Read Grep Glob
---
What's next for the kit build. $ARGUMENTS

**Read-only.** Change no files, branches or PRs, and don't start any work: report, then recommend
one prompt for the owner to send. (This is the repo's own dev tool and the prototype for the
installable `/next` in plan 07.)

## 1. Gather (run these; don't read whole files)
- `git status --short --branch`: current branch, ahead/behind, uncommitted files.
- `gh pr list --state open --json number,title,headRefName,url`; then `gh pr checks <n>` for each.
  If `gh` fails (not installed or not logged in), say so in one line and carry on without PRs.
- The table in `docs/plans/README.md` (the `| NN |` rows): number, title, status.
- `Grep` for `^\*\*Status:\*\*` in `docs/plans/[0-9][0-9]-*.md`: each plan file's own status.
- For the plan that is next (step 2): `Grep` its number (e.g. `plan 03`) in `docs/ARCHITECTURE.md`
  §15 *Open questions*, and read its own *Open questions* section if the file exists.

## 2. Work out the state, first match wins
1. **Uncommitted changes on `main`:** that's the first thing to sort out (work belongs on a branch).
2. **An open PR:** waiting on the owner's review. Name it, its CI result, and its plan.
3. **A plan file with Status Draft:** waiting on the owner's approval of the plan and its open
   questions.
4. **A plan Approved or In progress with no open PR:** building is under way; continue it.
5. **Otherwise:** the first plan in the index that is Not started is next.

## 3. Check the docs agree (report, never fix)
- An index row's status differs from its plan file's `**Status:**` line.
- A plan file not linked from the index, or an index link to a missing file.
- A plan marked Done whose branch still has an open PR, or a `plan/NN-*` branch checked out while
  that plan is Done.

## 4. Answer in about 15 lines, exactly this shape
```
**Where you are:** <branch> · <clean | N uncommitted> · <ahead/behind origin>
**Waiting on you:** <PRs to review (CI result) / draft plans to approve / open questions> or "nothing"
**Ready next:** Plan NN <title>: <one line on what it builds>
**Blocked:** <anything waiting on another plan> or "nothing"
**Docs that disagree:** <list> (omit the line if none)

**Recommended prompt:**
> <the exact message the owner could send next>
```

The recommended prompt follows the plan workflow: drafting a plan ("Draft plan 03 (protected paths)
following the plan workflow"), approving one ("Approved, go with your recommendations" plus a note
to read it first), or reviewing a PR ("Review PR #N; if approved, say so and I'll merge it"). Never
suggest skipping a review or approval step.
