---
name: kit-next
description: "Say where the kit's build stands and what to do next: branch and unfinished work, open PRs and CI, plans waiting on the owner, the next plan to start, and docs that disagree. Read-only; ends with one recommended prompt. Use for /kit-next, \"what's next\", \"where are we\"."
model: sonnet
effort: low
allowed-tools: Bash(git status *) Bash(git branch -vv) Bash(git rev-list --left-right --count main...HEAD) Bash(gh pr list *) Bash(gh pr checks *) Read Grep Glob
---
What's next for the kit build. $ARGUMENTS

**Read-only.** Change no files, branches or PRs, and don't start any work: report, then recommend
one prompt for the owner to send. Run commands from the repo root. (This is the repo's own dev tool
and the prototype for the installable `/next` in plan 07; named `kit-next` so it never shares a
name with the payload's skills, which Claude Code also loads here once a payload file is read.
Never run a payload skill in this repo.)

## 1. Gather
- `git status --short --branch`: current branch and uncommitted files.
- `git branch -vv`: every branch, its upstream, and whether it is ahead of it (unpushed).
- On a branch other than `main`: `git rev-list --left-right --count main...HEAD` (behind, ahead).
- `gh pr list --state open --json number,title,headRefName,url`, then `gh pr checks <n>` for each.
  `gh pr checks` exits non-zero when checks are failing or pending: that's a result to report, not
  an error. Only if `gh pr list` itself fails, say "PR status unavailable (gh)" and carry on.
- `Read` `docs/plans/README.md` (short): the `| NN |` rows give number (a split plan adds a letter: `07b`), title, status. Rows for
  plans not drafted yet have no link; that's expected. Rows marked `v0.2` are planned, not drafted.
  Its last **Build order** section (now v0.2's) lists the steps in order, naming plans and backlog
  item slugs;
  `Glob` `docs/backlog/done/*.md` shows which items are finished.
- `Grep` `^\*\*Status:\*\*` in `docs/plans/[0-9][0-9]*-*.md`: each plan file's own status.
- Only when step 2 lands on a plan (states 3–5): find its open questions with `Grep -i` for
  `^\|.*\bplans? ([0-9]{2}, )*NN\b` (NN = its number, e.g. `03`) in `docs/ARCHITECTURE.md`; those
  are the §15 table rows it owns. Also read its file's *Open questions* and `**Builds on:**` lines
  if the file exists.

## 2. Work out the state, first match wins
1. **Unfinished work without a PR:** uncommitted changes on any branch, or a branch other than
   `main` that is ahead of `main` and has no open PR. Name the branch and what it holds (its last
   commit subject, shown by `git branch -vv`); the next step is to finish, commit, push and open its PR.
2. **An open PR:** waiting on the owner's review. Name it, its CI result, and its plan.
3. **A plan file with Status Draft:** waiting on the owner's approval of the plan and its open
   questions.
4. **A plan Approved or In progress:** building is under way; continue it.
5. **The first unfinished step in the index's last Build order** is next: a plan that isn't Done,
   or a step whose backlog items aren't all in `docs/backlog/done/` (name the first one left). If
   none is left, say that release is complete and recommend reviewing the roadmap and cutting it.

**Blocked** lists only a plan whose `**Builds on:**` names a plan that isn't Done; otherwise
"nothing". Don't guess dependencies.

## 3. Check the docs agree (report, never fix)
- An index row's status differs from its plan file's `**Status:**` line.
- A plan file not linked from the index, or an index link to a missing file.
- A plan marked Done whose branch still has an open PR.

## 4. Answer in about 15 lines, exactly this shape
```
**Where you are:** <branch> · <clean | N uncommitted> · <N ahead / N behind main> · <pushed | N unpushed | not pushed (no upstream)>
**Waiting on you:** <PRs to review (CI result) / draft plans to approve / open questions> or "nothing"
**Ready next:** <unfinished branch to wrap up, or Plan NN <title>: one line on what it builds>
**Blocked:** <plan and what it waits on> or "nothing"
**Docs that disagree:** <list> (omit the line if none)

**Recommended prompt:**
> <the exact message the owner could send next>
```

The recommended prompt follows the plan workflow: finishing a branch ("Review and push
<branch>, then open its PR"), drafting a plan ("Draft plan 03 (protected paths) following the plan
workflow"), starting a backlog item ("Do the backlog item <slug> following the plan workflow"), approving one ("Approved, go with your recommendations", after reading it), or
reviewing a PR ("Review PR #N; if approved, say so and I'll merge it"). Never suggest skipping a
review or approval step.
