# Decisions log

Why the kit is built the way it is. Newest first. Each entry: date, the choice, why, and what it affects.
The current design lives in `docs/ARCHITECTURE.md` (once written) and `docs/ROADMAP.md`; this file records *why*.

## 2026-10-04: Best-practice review (plan 00)

10. **Hall of Echoing Mirrors is a reference, not a spec.** It was a first attempt. Where it and
    current best practice disagree, best practice wins; `survey-hoem.md` is kept for its lessons.

11. **Lanes are long-lived workspaces; branches are short-lived, one per task.** A lane keeps its
    worktree folder, scope, owned paths and tool ports. Each task runs `lanes start <task>`, which
    creates `<lane>/<task>` from the latest integration branch, after checking the previous task branch
    was merged. *Why:* long-lived lane branches drift (they fall behind, and after a squash-merged PR
    their old commits never match `main`). Branches that live for one task can't drift. A prompt step
    in `/wrap-up` alone wouldn't fix it: it can be skipped, and in PR mode the merge hasn't happened yet
    when it runs. So the logic lives in tested CLI commands, and the SessionStart hook reports drift.

12. **`lanes finish` defaults to PR mode:** run tests, push, open a pull request carrying the reviewer
    report, merge after CI. **Local mode** (fast-forward the integration branch with
    `git push . HEAD:<branch>`, from the first implementation) stays as an option for solo or offline
    work. *Why:* industry practice is branch → PR → CI → human review; verification is now the
    bottleneck, not generation.

13. **No shared append-only files.** Changelog entries are fragments (`docs/changelog.d/<branch>.md`)
    compiled at release. Backlog items are one file each (`docs/backlog/<slug>.md` with a small header:
    status, lane, size), like plans already are. `BUILD-STATE.md` is regenerated, never hand-merged.
    *Why:* every lane's wrap-up edited the same files, the main source of merge conflicts.
    Fragments (the towncrier/changesets pattern) make those conflicts impossible; `merge=union` was
    considered and rejected as fragile.

14. **Every check is one Python module with three entry points:** a Claude Code hook (JSON on stdin),
    a command a human or agent runs on files or a diff, and a git pre-commit check. CI runs the same
    command. *Why:* Claude Code hooks only cover Claude Code sessions; edits from other agents
    (which read `AGENTS.md`), humans, or skipped hooks must hit the same rules (defence in depth).

15. **Permission deny rules are the primary protection; the protected-paths hook is a backstop.**
    Shell-command pattern matching is easy to get around, so the hook guards against mistakes, not
    adversaries. The README states what it does not stop and recommends Claude Code's sandbox for a
    real boundary. *Why:* honesty about guarantees; overclaiming would cost credibility.

16. **Scenario tests ("evals") run real Claude Code sessions** (`claude -p`) against the example
    project: the reviewer catches a planted bug, the hook blocks a force-push, and so on. Run on demand
    or nightly, not on every push (they cost tokens). *Why:* tests of the Python prove the scripts
    work; only evals prove the prompts and wiring work.

17. **Into MVP:** the CI template for installed projects (cheap once checks have a CLI entry point),
    `/next` (lane-aware what's next), and `/onboard`. **The installer is deterministic; `/onboard` is
    agentic:** the installer lays down structure and asks only what it can't detect, then `/onboard`
    has Claude read the repo and fill project-specific content (stack, test command, path-scoped rules)
    for the owner to approve.

18. **The kit is built with its own process:** numbered plans in `docs/plans/`, one branch and PR per
    plan, each PR carrying a fresh-context review. *Why:* the plan → PR → review trail is the evidence
    a reviewer of this repo will look for.

19. **The installer writes the full path of a real Python interpreter** into hook commands. *Why:* on
    Windows, `python` can be the Microsoft Store alias, which opens the Store instead of running;
    `python3` often doesn't exist on Windows and `python` often doesn't on macOS.

20. **Relation to Claude Code agent teams:** lanes are for persistent, human-supervised parallel
    workstreams; agent teams are for one-off fan-out inside a task. They are complementary; the
    README explains when to use each.

## 2026-10-04: Project kickoff decisions

1. **Audience: generic software projects first, Unity as an add-on pack.** The kit should be useful to
   any team; Unity is the case it was born from and stays a first-class pack. *Why:* broader showcase
   value, and the lane workflow isn't Unity-specific.

2. **Lane worktrees live in Claude Code's default location, `.claude/worktrees/<lane>/`.** *Why:* it
   matches `claude --worktree`, so the kit builds on the native feature instead of competing with it.
   The README documents how to move them to sibling folders (`../project-<lane>/`), which Unity setups
   usually want (one editor per folder, no nested project copies for scanners).

3. **Python is the one implementation language** for setup, the lanes CLI and every hook, with thin
   `install.ps1` / `install.sh` bootstrappers that only check prerequisites and hand off.
   *Why:* hooks already need Python; one codebase means one pytest suite and no drift between a
   PowerShell and a bash copy. **Standard library only, Python 3.11+** (for `tomllib`), so installed
   projects never need `pip install`.

4. **Generate `AGENTS.md` as well as `CLAUDE.md`.** Universal rules go in `AGENTS.md` (read by Codex,
   Cursor, Copilot, Gemini and others); `CLAUDE.md` imports it with `@AGENTS.md` and adds
   Claude-specific parts (skills, hooks, lanes). *Why:* one source for rules any agent should follow.

5. **The example project is a small Python project.** *Why:* the repo is a portfolio piece; a reviewer
   should be able to clone it and run it in a minute without Unity installed.

6. **GitHub repo created now, private until the MVP works, then made public.** Every step is committed
   as it's built, so the history shows the process. *Why:* incremental history reads well to reviewers;
   a half-built public repo reads worse than a finished one with history. Flipping to public keeps all
   history.

7. **Kit-owned vs project-owned files.** Files the kit owns (skills, reviewer, hook scripts, lanes CLI)
   are recorded in a manifest with their hashes, so a later `update` can replace them safely and spot
   local edits. Project-owned files (`CLAUDE.md`, `AGENTS.md`, rules, configs, docs) are filled in once
   and never overwritten. *Why:* makes the update command and plugin packaging cheap later.

8. **Human-edited config is TOML** (`lanes.toml`, rules-check patterns), read with `tomllib`.
   *Why:* comments allowed, stdlib reader, friendlier than JSON for hand edits.

9. **Fail modes differ per hook.** The rules-check hook fails *open* (a crash never blocks an edit).
   The protected-paths hook fails *closed* (a broken config blocks with a clear message), because a
   guard that silently switches off is worse than a noisy one.
