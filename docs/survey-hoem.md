# Survey: the Hall of Echoing Mirrors setup

Build step 1. Every workflow file in the source project (a Unity 6 game built with Claude Code across
three parallel lanes), sorted into what the kit takes and how. Surveyed 2026-10-04.

**Legend:** **Kit** = kit-owned, generalized, replaceable on update · **Template** = project-owned,
filled in once by setup · **Unity** = Unity pack · **Example** = shipped as a sample to copy, not
installed · **Leave** = specific to that game.

## Instructions

| Source | Becomes | Notes |
| --- | --- | --- |
| `CLAUDE.md` (68 lines, ~1,100-word budget) | Template `CLAUDE.md` + `AGENTS.md` | Keep its shape: brief, current stage, where things are, environment, checking your work, hard rules, working with the user, compact instructions. Universal hard rules move to `AGENTS.md`. Keep the "propose edits to this file, never append on your own" rule and the size budget. |
| `PROJECT_NOTES.md` (user preferences, placeholder list) | Template, optional | Generalize to "preferences + placeholder rules to revisit". |
| `.claude/rules/design-docs.md` | Template | Generic: vision / design doc / decisions log / plans. Uses `paths:` frontmatter. |
| `.claude/rules/simulation.md`, `ui.md`, `content.md`, `editor-tools.md` | Example | Good samples of path-scoped rules ("put a new rule in the matching file" tables, helper lists). |
| `docs/CODE-STANDARDS.md` | Template | §6 "Don't over-engineer" and the severity scale are universal; §3 Unity → Unity pack; §4 C# → stack pack. |
| `docs/ai/WORKFLOW.md` (221 lines) | Template | The "why" guide. Sections 1–8 generalize well; strip game examples. |

## Skills

| Source | Becomes | Notes |
| --- | --- | --- |
| `plan-feature` | Kit | Drop VISION pillar / GDD § specifics → "design docs, if present". Keep: subagent finds code, interview, park future work in backlog, ≤8 steps or split, stop for approval. |
| `implement` | Kit | Keep: Approved-status check, stop on unsettled design, failing tests first, nothing beyond the plan. |
| `wrap-up` | Kit | Step 3 (docs) is long and game-shaped; split into the universal core plus a project hook ("extra docs to update" listed in config or CLAUDE.md). |
| `code-health` | Kit | Area split → derived from `.claude/rules/` paths or lane scopes. |
| `design` | Kit | Generalize GDD → design doc; keep "never read whole, grep the §". |
| `refactor`, `sync-state`, `workflow` | Kit (Later) | `sync-state` structure is game-specific; ship a generic "what the build does now" skeleton. |
| `next` | Kit (**not in the original feature list**) | Lane-aware "what's next": reads the shared branch's backlog/plans, buckets ready / waiting on you / blocked. Strong fit for the lanes differentiator. Proposed for MVP or early Later. |
| `ui-work`, `writing` | Example | Role skills: show the pattern ("read only these folders, token budget, don't read X"). |
| `balance` | Leave | Game-specific. Its "Traps" section is a good pattern to document. |
| Frontmatter conventions | Kit | `model:` per skill (Opus to plan/design, Sonnet to build), `effort:`, `argument-hint:`, `disable-model-invocation: true` on skills with side effects, `allowed-tools:` for read-only skills. |

## Subagent

| Source | Becomes | Notes |
| --- | --- | --- |
| `.claude/agents/reviewer.md` | Kit + checklist files | Checks 6 (tests), 7 (error hiding), 9 (plan conformance/scope), 10 (silent design decisions), 1 (duplication, minus named helpers), 11 (standards) → universal. Checks 2–5 → project checklist (template). Check 8 → Unity pack. Keep the severity scale, "judge only changed lines; untouched code goes under Seen nearby", "over-engineering is a defect too", max 5 polish items, one-line verdict. |

## Hooks

| Source | Becomes | Notes |
| --- | --- | --- |
| `check-code-rules.py` (PostToolUse) | Kit: rules-check | Patterns move from code to TOML config (pattern, glob, message). Already fails open, ignores `//` comments, exits 2. Generalize comment syntax per file type. Its two Unity patterns become the Unity pack's sample config. |
| `lane-context.py` (SessionStart) | Kit: lane-router | Reads the lane table from a Markdown file today; switch to `lanes.toml` and generate the doc table from it. "Editor" → generic per-lane tools/port. Already never blocks. |
| SessionStart role reminder (`echo` systemMessage) | Drop | Notes say it never displayed in the desktop app. |
| *(none)* | Kit: protected-paths (new) | Source relied on permission deny rules only. |

## Settings and safety

| Source | Becomes | Notes |
| --- | --- | --- |
| `.claude/settings.json` hooks block | Kit-generated | Interpreter (`python`/`python3`/`py`) chosen by setup; quote `$CLAUDE_PROJECT_DIR` (paths with spaces). |
| permissions allow (git read commands, grep, ls) | Template | Both `Bash(...)` and `PowerShell(...)` forms. |
| permissions deny/ask (Library, Temp, `.meta`, scenes) | Unity | |
| `.gitignore`, `.gitattributes` (LF, binaries, linguist-generated) | Template + Unity | Base `.gitattributes` with `eol=lf`; Unity adds its binary list. |

## Lanes

| Source | Becomes | Notes |
| --- | --- | --- |
| `docs/parallel-lanes.md` | Template (generated table) + Kit CLI | The lane table becomes `lanes.toml`; the doc keeps the human workflow. |
| Shared integration branch (`backlog-tasks`), updated only by local fast-forward `git push . HEAD:<branch>` | Kit: `lanes merge` | Core of the merge design. Configurable `integration_branch` (default `main`). Fast-forward-only means finished work can't be overwritten; refused → sync and retry. |
| "Starting a task" / "Finishing a task" steps | Kit skills step 0 + `lanes sync`/`merge` | Every skill starts with the lane check. |
| Conflict policy (append-only docs keep both sides; status doc regenerated; binary/scene → stop and ask) | Kit | Improvement: `.gitattributes merge=union` for append-only docs (CHANGELOG, BACKLOG) so git does it automatically. |
| Copy `settings.local.json` into each worktree | Kit | Use Claude Code's `.worktreeinclude`. |
| Auto-memory is per folder → junction each worktree's memory to the main one | Kit (optional step in `lanes create`) | Windows junction / Unix symlink. |
| `git update-index --skip-worktree .vscode/settings.json` | Unity | Unity rewrites it per folder name. |
| Close scenes before git commands that touch them (SceneGitGuard) | Unity docs | Editor freezes on "modified externally". |
| RAM notes, batch-mode test command | Unity docs | |
| One active session per folder; stop if files change that this session didn't touch | Kit (rule) | |

## Unity pack material

`.mcp.json` (standalone HTTP MCP at `127.0.0.1:8080`), `tools/unity-mcp.ps1`, `docs/unity-mcp-connection.md`,
Unity `.gitignore`, reviewer check 8, rules-check patterns, permission deny/ask list, per-lane editor
instance selection (`set_active_instance`), the scene/skip-worktree/RAM notes above.

## Lessons from the workflow notes, built into the kit

1. Deny patterns starting `./` anchor to the session's working directory, not the project root, so
   they silently failed in a session started in a subfolder. **Kit: use root-anchored patterns and test
   them.** (Verify exact syntax against current docs before shipping.)
2. ~40% of Bash calls began with `cd "D:/..." &&`, which also drove permission prompts. **Kit:
   `AGENTS.md` says the shell starts at the project root; never prefix commands with `cd`.**
3. `systemMessage` from SessionStart didn't show in the desktop app; whether `additionalContext`
   reaches the model there was untested. **Kit: verify both in CLI and desktop, document the result.**
4. Bloated context drove cost: one session used 69% of all tokens. **Kit: one task per session,
   `/clear` suggestions in every skill's last step, subagents for reading.**
5. Budgets keep instructions lean: `CLAUDE.md` word cap, rules files ≤200 lines, plans ≈ one screen.
