# Survey: Claude Code's built-in features

What Claude Code already does that the kit would otherwise build, and what constrains the kit's
plans. Read from the official docs ([index](https://code.claude.com/docs/llms.txt)) on 2026-10-05,
in four areas: evals and CI; plugins and distribution; parallel sessions; hooks, permissions and
skills. Companion to [survey-lanekeeper.md](survey-lanekeeper.md).

> **Reference, not spec, and it goes stale fast.** Claude Code ships weekly; recheck a page before
> a plan relies on it (CLAUDE.md: check the current docs). ✓ marks claims checked word for word
> against the raw page; the rest come from research agents quoting the docs and need the same check
> before use. Tool summaries of doc pages have invented fields before: read the raw `.md`.

## Decisions to revisit (owner's call)

Settled since, on Claude's recommendation: 30 and 31 by decision 82; 57 by decision 78 (the plugin
waits for v0.2); 35 was checked live on Linux and Windows and isn't a bug (decision 84).

| Decision | What the docs say | Suggested action |
| --- | --- | --- |
| 30: kit config gets ask rules, plus a hook block only in `bypassPermissions`, because "ask rules don't prompt in bypass mode" | ✓ Claude Code "doesn't auto-approve the following in any mode, including `bypassPermissions`: Tools matched by an explicit ask rule" ([permission-modes](https://code.claude.com/docs/en/permission-modes.md)). The reason no longer holds | Live-check once, then drop the bypass hook block or restate the reason. Also answers ARCHITECTURE §15 "do ask rules prompt in acceptEdits?": yes |
| 31: secrets default to `.env`, `.env.local`, `.env.*.local`, because an allow can't carve out `.env.example` | ✓ "A deny or ask pattern that starts with `!` is a gitignore negation", within one settings file's list ([permissions](https://code.claude.com/docs/en/permissions.md)) | Consider `.env.*` plus `!.env.example` as the default |
| 35: `lanes create` writes `claudeMdExcludes` into the **lane's own** `.claude/settings.local.json` | ✓ In a worktree, Claude Code "uses the file at the main checkout's root"; the file stays with the worktree only "on Windows" and a few other cases ([settings](https://code.claude.com/docs/en/settings.md)). Verified live on Windows only | **Likely bug on macOS/Linux:** lanes may read the main checkout's file instead. Live-check there before plan 08 (backlog `lane-settings-cross-platform`) |
| 57: the reviewer is read-only through a `PreToolUse` hook in its own frontmatter | ✓ Plugin agents ignore `hooks` frontmatter: "An agent file can't add hooks or MCP servers on its own" ([plugins/components](https://code.claude.com/docs/en/plugins/components.md)). ✓ Frontmatter hooks are skipped until the folder is trusted ([sub-agents](https://code.claude.com/docs/en/sub-agents.md)) | If the kit becomes a plugin, move the guard into the plugin's `hooks/hooks.json`, gated on the hook input's `agent_type` (the value for a plugin agent isn't documented: test it), or keep the reviewer installed in `.claude/agents/` |
| 70 (plan 07): skill `model` and `effort` kept only if they work | ✓ Both are documented skill fields ([skills](https://code.claude.com/docs/en/skills.md)); `model` "applies for the rest of the current turn". Caveat: auto mode skips a model it doesn't support | Keep both; re-run plan 07's observation outside auto mode |

## By plan and backlog item

### Plan 08 and `ship-kit-as-plugin`

| Built-in | What it means for the kit |
| --- | --- |
| Marketplace from the kit's own repo; projects list it in `extraKnownMarketplaces` and `enabledPlugins` in `.claude/settings.json` ([plugins/org](https://code.claude.com/docs/en/plugins/org.md)) | Replaces the installer's copy step and the update command for kit-owned files. Teammates must trust the folder; external sources need `claude plugin install … --scope project` each |
| `version` per release, or the commit SHA; pinning by ref/sha; auto-update **off** by default for third-party marketplaces ([plugins/publish](https://code.claude.com/docs/en/plugins/publish.md)) | Replaces the hash manifest for kit-owned files. Teams drift unless the README says how to update |
| `userConfig` options reach hooks as `CLAUDE_PLUGIN_OPTION_<KEY>`; `${CLAUDE_PLUGIN_DATA}` survives updates ([manifest-reference](https://code.claude.com/docs/en/plugins/manifest-reference.md)) | Replaces the machine-local `.claude/kit/python-path`. Per user, so it can't replace `kit.toml` |
| ✓ `bin/` is on the PATH of "the Bash tool's shell" only, after the user's own PATH ([plugins/components](https://code.claude.com/docs/en/plugins/components.md)); paths change on update | Claude can run `kit`; people's own terminals, git pre-commit and CI can't. The checks still need a project-local or pip install route |
| A plugin's `settings` applies only `agent` and `subagentStatusLine`; a `CLAUDE.md` in the plugin isn't loaded; no install or first-run event | A setup step (`/worklanes:setup` or `kit init`) still writes `kit.toml`, deny rules, `CLAUDE.md`/`AGENTS.md`, `.claude/rules/`, docs, and the marketplace entries, never overwriting |
| Uninstalling deletes options and the data folder, never project files ([plugins/cli-reference](https://code.claude.com/docs/en/plugins/cli-reference.md)) | Kit uninstall shrinks to project cleanup (backlog `doctor-and-uninstall`) |
| Plugin dependencies with version ranges ([plugins/dependencies](https://code.claude.com/docs/en/plugins/dependencies.md)) | Plan 10: a pack can be its own plugin that depends on `worklanes` |
| `claude plugin details` shows each skill's always-on token cost; `/skill-doctor` flags unused skills ([plugins/measure](https://code.claude.com/docs/en/plugins/measure.md)) | Keep the skills' descriptions cheap once the kit is a plugin |
| Hook command forms: shell form uses Git Bash on Windows when installed, else PowerShell; exec form needs a real `.exe`; per-hook `shell: "powershell"` ([hooks](https://code.claude.com/docs/en/hooks.md)) | Keep the `sh` launcher; `shell: "powershell"` is one answer to §15's "`sh` missing" row |

### Plan 09 (CI template) and `ci-check-annotations`

- **Claude Code GitHub Action** (`anthropics/claude-code-action@v1`, [github-actions](https://code.claude.com/docs/en/github-actions.md)): its `prompt` input can invoke a skill. Optional extra job (for example the reviewer); the required checks stay plain Python with no token cost. Secrets are withheld from fork PRs.
- **Managed Code Review** ([code-review](https://code.claude.com/docs/en/code-review.md)): Team/Enterprise preview, about $15–25 a review, reads `CLAUDE.md` and a root `REVIEW.md`, and "never blocks merging". The kit's checks stay the only blocking gate. Idea: generate `REVIEW.md` from `.claude/review/` (backlog `review-md-from-checklists`).
- Only managed Code Review writes check-run annotations, so `kit check --github` is still needed.

### Plan 11 (evals)

- ✓ **`claude plugin eval`** ([plugin-evals](https://code.claude.com/docs/en/plugin-evals.md)) is a full harness: three runs per case, a no-plugin baseline, graders (`regex`, `tool_used`, `tool_order`, `file_exists`, `llm`, `baseline`; "There are no custom-code graders"), a cost ceiling, JSON output and exit codes for CI.
- ✓ But "**Nothing personal or project-level loads**": no `.claude/`, no `CLAUDE.md`, "even one a `scaffold_script` wrote". It can't test the kit as installed into a project, only what ships in a plugin.
- ✓ "Native Windows has no backend, so run shell-granting suites under WSL2".
- **So:** plan 11 keeps its own `claude -p` harness for whole-project scenarios, and borrows the eval design (repeat runs, baseline, cost cap, JSON exit codes). If the kit becomes a plugin, its skills and reviewer can also get a plugin-eval suite. Which to build first is the owner's call.
- ✓ **`--bare` "will become the default for `-p` in a future release"** and skips hooks, skills and `CLAUDE.md` ([headless](https://code.claude.com/docs/en/headless.md)). Every live check and eval must state what it loads, and assert it from the `system/init` event (`plugins`, `plugin_errors`).
- ✓ A `-p` run executes project `settings.json` hooks even in an untrusted folder, but skips agent frontmatter hooks until the folder is trusted. Evals that need the reviewer's guard must trust the folder first and check that the guard loaded.

### Lanes (`lane-resources-env`, `lanes-and-worktree-flag`, ROADMAP §6 Later)

- ✓ **`CLAUDE_ENV_FILE`**: a SessionStart hook can append `export` lines that apply to later Bash commands ([hooks](https://code.claude.com/docs/en/hooks.md)). The lane-router can hand a lane its ports with no new CLI. Not documented for the PowerShell tool (test it); doesn't reach the user's own terminal, so a lane `.env` is still needed.
- ✓ **`sessionTitle`** from SessionStart sets the session's name "from the launch folder, git branch, or worktree name". Name each session after its lane, which also makes it reachable by name in cross-session messaging.
- ✓ **Status line** gets `workspace.git_worktree` for any linked worktree ([statusline](https://code.claude.com/docs/en/statusline.md)). An optional status line could show lane, task branch and drift.
- **Cross-session messaging** ([cross-session-messaging](https://code.claude.com/docs/en/cross-session-messaging.md)) lists "Coordinate parallel worktrees" as a use. It covers live lane-to-lane coordination; it isn't stored, so persistent handoff notes (§6 Later) remain files.
- **Lane memory:** all worktrees share one auto-memory folder ([memory](https://code.claude.com/docs/en/memory.md)); a gitignored `CLAUDE.local.md` exists only in its own worktree, a cheap place for lane notes.
- **Desktop preview:** `.claude/launch.json` per folder with `autoPort` ([desktop](https://code.claude.com/docs/en/desktop.md)); `lanes create` could write a lane's fixed port there.
- **Background sessions** started inside a linked worktree don't make another one ([agent-view](https://code.claude.com/docs/en/agent-view.md)), so `claude --bg` works in a lane folder. Check live that deleting a session never removes a lane folder.
- **Don't use a `WorktreeCreate` hook for lanes:** it receives only `name`, replaces creation for every subagent and background session too, and turns off `.worktreeinclude`.
- **Agent teams** don't isolate teammates in worktrees and are experimental: not a fit for lanes.

### Hooks and protected paths

- Built-in Bash rules already split compound commands, strip `timeout`/`nice`/`nohup`/`command`/`xargs`, and match past `VAR=` prefixes. But a rule "isn't a security boundary around the program": `git -C . push`, `git -c … push` and quoted words slip past, and the docs recommend a PreToolUse hook for full-text checks ([permissions](https://code.claude.com/docs/en/permissions.md)). Both the deny rules and the backstop stay (decision 28).
- `Read`/`Edit` deny rules now also apply to Bash file commands Claude Code recognizes (`cat`, `head`, `tail`, `sed`, `tee`) and to redirection targets. The backstop's Bash file-command checks overlap; narrow them or keep them as a drift guard, and say so.
- ✓ Only `Edit(path)` and `Read(path)` path rules are consulted; a `Write(...)` path rule is accepted but never used. `kit settings sync` must emit only those two.
- Writes to `.git`, `.claude` (except `.claude/worktrees/`), `.husky` and `.pre-commit-config.yaml` are never auto-approved outside `bypassPermissions`; `kit.toml` and `.githooks/` aren't on that list, so the kit's ask rules for them stay.
- A hook's `"if": "Bash(git *)"` field skips spawning the hook when the call doesn't match: fewer Python starts (backlog `hook-if-conditions`).
- ✓ The sandbox "runs on macOS, Linux, and WSL2. On native Windows, Claude Code runs commands unsandboxed" ([sandboxing](https://code.claude.com/docs/en/sandboxing.md)). `protected-paths.md` should name the Windows options: WSL2, a container or a VM.

### Skills, reviewer and instructions

- `allowed-tools` "does not restrict which tools are available"; `disallowed-tools` does ([skills](https://code.claude.com/docs/en/skills.md)).
- Bundled `/code-review` (and `ultrareview` for CI) hunt bugs; the kit's reviewer checks against the plan, the rules and the checklists. Say so in the README (backlog `readme-builtins-comparison`); `/wrap-up` could suggest `/code-review` as a second pass.
- `AGENTS.md` is read natively only when no `CLAUDE.md` exists; the `@AGENTS.md` import never double-loads it, and is preferred over a symlink on Windows. Keep the template. Path-scoped rules trigger on Read/Write/Edit, not on Bash.
- `/doctor prompt-audit` audits instruction files: `/code-health` (07b) can call it instead of re-auditing instructions.
- The official `security-guidance` plugin pattern-checks edits and reviews diffs but blocks nothing, and recommends "a hook that blocks the edit or a CI check" for enforcement: what the kit's protected-paths hook is.

## Repo docs this makes stale

- `docs/ARCHITECTURE.md` §15 says the plugin eval docs page isn't published yet: it is.
- §15's "do ask rules prompt in acceptEdits?" is answered (yes; see decision 30 above).
