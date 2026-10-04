# 00 — Architecture and plan series

**Status:** In progress
**Branch / PR:** `plan/00-architecture`
**Builds on:** `docs/decisions-log.md` (2026-10-04 kickoff), `docs/survey-hoem.md`

## Goal
Settle the decisions every later plan depends on (repo layout, kit-owned vs project-owned files, the
lane model, config formats, how checks run) in one reviewed document, and split the remaining work
into a numbered series of plans, one PR each.

## Out of scope
- Any code, template or skill. Those start in plan 01.

## Open questions
- None blocking. Questions found while writing are listed at the end of `docs/ARCHITECTURE.md`
  and assigned to the plan that must answer them.

## Reuse
- `docs/survey-hoem.md`: lessons and patterns from the first implementation (reference, not spec).
- Current Claude Code docs, checked for this plan: permissions, sandboxing, hooks, skills, subagents,
  worktrees, plugins, headless mode.

## Changes
| File | New / Edit | What |
| --- | --- | --- |
| `docs/ARCHITECTURE.md` | New | The design: layout, ownership, lane model, configs, checks, installer, distribution |
| `docs/plans/README.md` | New | Plans index: the series 00–12 and their status |
| `docs/plans/_TEMPLATE.md` | New | The kit's plan format (later shipped as a template, plan 01) |
| `docs/plans/00-architecture.md` | New | This plan |
| `docs/decisions-log.md` | Edit | Decisions 10–20 from the best-practice review |
| `docs/ROADMAP.md` | Edit | Scope changes: PR-mode merge, task branches, fragments, CI template and `/next`, `/onboard`, evals in MVP |
| `docs/survey-hoem.md` | Edit | Reframed as reference, not spec; superseded items marked |
| `README.md`, `CHANGELOG.md` | Edit | Status table; Unreleased entry |

## Steps
1. Verify the Claude Code facts the design relies on against current docs.
2. Write `ARCHITECTURE.md`.
3. Update decisions log, roadmap, survey, README, changelog.
4. Independent review in a fresh context; fix findings.
5. Open the PR and stop for the owner's review.

## Tests
| Test | Proves |
| --- | --- |
| `tests/test_repo_basics.py` (existing) | Repo invariants still hold |
| `tests/test_plans.py` (new) | Every plan in the index exists, and every plan file has a Status line |

## Done when
- [x] ARCHITECTURE.md covers layout, ownership, lanes, configs, checks, installer, distribution, testing
- [x] Plans 01–12 listed with scope and order
- [x] Reviewer report attached to the PR
- [ ] Owner approves the PR

## Notes after implementation
<!-- Filled in at wrap-up. -->
