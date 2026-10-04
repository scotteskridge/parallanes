# Decisions log

Why the kit is built the way it is. Newest first. Each entry: date, the choice, why, and what it affects.
The current design lives in `docs/ARCHITECTURE.md` (once written) and `docs/ROADMAP.md`; this file records *why*.

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
