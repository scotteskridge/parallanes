# Decisions log

Why the kit is built the way it is. Newest first. Each entry: date, the choice, why, and what it affects.
The current design lives in `docs/ARCHITECTURE.md` (once written) and `docs/ROADMAP.md`; this file records *why*.

## 2026-10-06: Live checks say what they load

93. **Live checks are pytest tests under `tests/live/`, marked `live` and run only with `--live`;
    each goes through `tests/live/claude_run.py`, which pins and asserts what the session loads.**
    Settled on Claude's recommendation (backlog `live-checks-pin-what-loads`):
    - Never in CI or the normal test commands: they cost money and need the owner's login.
    - Every run passes `--setting-sources project,local` (the owner's `~/.claude` stays out), an
      explicit `--permission-mode` and `--model` (`haiku` by default), and `--max-budget-usd`
      (1 USD by default).
    - It asserts skills, agents and plugins from `system/init` and hooks from `hook_started`
      events (`--include-hook-events`): checked live with Claude Code 2.1.291, `system/init` lists
      skills and agents by name but has no `hooks` field. *Why:* `--bare` will become the `-p`
      default with no opt-out flag, and would make a check pass while testing nothing.
    - Each check reuses a fixed folder under the temp folder (`kit-live/<check>`), so the owner
      accepts a trust dialog once; the helper only reads `~/.claude.json` (or
      `$CLAUDE_CONFIG_DIR/.claude.json`) to check trust, never writes it.
    - *Review round 1:* a run must end in a `success` result unless the check asks for an error
      (a run stopped by the budget or turn cap would pass "nothing changed" assertions); trust
      must be on the exact folder, since nothing shows Claude Code passes it down; a hook is
      named as the stream names it (`PreToolUse:Edit`), and `expect_hooks` only shows the session
      wasn't stripped down, so a check relying on one particular hook needs a canary of its own;
      `--live` replaces `-m live`, which `-m "not (slow and live)"` would have tripped; a `.cmd`
      shim is refused, since cmd.exe mangles prompts. Personal skills stay out under
      `--setting-sources project,local`: the owner's `~/.claude/skills/unity-mcp-skill` was absent
      from a pinned run's `system/init`. Plan 11 keeps its own harness design but follows these
      rules.

    Decision 92's ask-rule check is the first one. Its first run under the helper failed on a
    broken scratch project (no Edit call, so the canary hook never fired), which is the point.

## 2026-10-06: Permission decisions, checked against the docs

92. **The hook's bypass-mode block for kit config covers shell commands only; secrets
    exemptions are bare `!` names.**
    Replaces decision 30's bypass block and decision 31's list, as decision 82 planned. Settled on
    Claude's recommendation (backlog `revisit-permission-decisions`):
    - *Live check,* Claude Code 2.1.291, Windows, `claude -p` in a scratch project with an ask rule
      on one file, a deny rule on another and a third file with neither: in `bypassPermissions` and
      in `acceptEdits` the asked edit was refused (listed in the run's `permission_denials`) and the
      free one went through. A control run in bypass mode without the ask rule changed the file. So
      ask rules are never auto-approved; headless, nobody can answer, so the call is refused.
    - *Review round 1 (🔴):* the old block also stopped shell writes to kit config (`rm -rf
      .githooks`, `Set-Content .claude/settings.json`), and the ask rules are `Edit` rules the docs
      don't say cover those; the live check used the Edit tool only. So the hook still blocks
      shell write and remove targets in kit config, and leaves file tools to the ask rules.
      *Rounds 2-3:* `acceptEdits`, `auto`, `dontAsk` and allow-listed commands have the same gap.
      Round 2 widened the block to those modes and counted a write into a folder as a write to
      everything in it, which blocked everyday commands such as `cp file .`; both were undone.
      (`git restore --staged .` is still blocked in bypass mode, as before this decision.) Which
      modes the block should cover is left to the owner (backlog
      `kit-config-shell-guard-modes`); until then it stays as before this decision, and
      `protected-paths.md` lists the gap under Known misses.
    - An exemption is allowed only in `secrets`, only as a bare file name (no folder, no trailing
      `/`), only after a bare name it matches (a wildcard exemption: after any bare name), and a secret
      may not be listed twice, `./` ignored; anything else
      is a config error. *Why:* Claude Code carves a `!` rule only out of unanchored rules listed
      before it, and the kit anchors every rule with a folder or a trailing `/`, so any other
      exemption would silently do nothing. The hook and `kit check protected` apply the same rule,
      so they agree with the deny rules.
    - `kit settings sync` keeps `kit.toml`'s order around each exemption: a new name goes in front
      of an exemption already there, a name listed after it stays after it, and rules reordered by
      hand are put back (also an owner's copy: only positions change). `kit check settings` reports
      an exemption out of order. Every path rule it writes is `Read(...)` or `Edit(...)`, the only
      kinds Claude Code consults; a test holds it there.
    - The hook's overlap with the deny rules stays, labelled a drift guard: it covers a stale
      `settings.json` and PowerShell cmdlets, which the docs don't say deny rules cover.

## 2026-10-06: Plan 07b questions

91. **`/code-health` starts its task branch before the audit.** *The owner's call at review round 2:*
    a lane that is behind would otherwise audit old code and file its report, with `path:line`s
    that may have moved, on the newer integration tip; and a `lanes start` that refuses (unmerged
    work) now stops it before any subagent runs. Cost: an empty branch when the owner keeps
    nothing, which the next `lanes start` removes. A read-only `auditor` agent instead of
    `Explore` waits in the backlog (`auditor-agent`).

90. **07b runs a lighter process:** at most five open questions, one review round (another only for
    a 🔴), one headless live run per skill. *Why:* two small skills don't need plan 07's weight;
    a trial of backlog `lighten-plan-process`.

89. **`/design` edits `DESIGN.md` where it is and changes no branches.** In a lane the ownership hook
    asks once per edit, since `DESIGN.md` isn't shared; on the integration branch, or a lane
    between tasks, the skill stops and says to start a task first. Without a `DESIGN.md` the
    decision goes only in the decisions log, and the file is created only when the owner asks. *Why:* a design change is rare and the
    owner is present for it; one prompt is the right friction.

88. **`/code-health`'s report and the backlog items the owner picks are committed on their own task
    branch, and `docs/health/**` is a default shared path.** The report is
    `YYYY-MM-DD-<lane>-<area>.md` (`<area>` a slug of the narrowed area, or `all`; no lane part
    without lanes), the branch `health-YYYY-MM-DD-<area>` (a lane's branch has its prefix already),
    `-2` if taken (review rounds 1-2: two lanes on one day would otherwise collide). *Why:* a new file per run doesn't conflict (decision 13), and the
    report goes through the same loop as any change.

87. **`/code-health` audits by area with parallel subagents** (`Explore`: it can't Edit or Write,
    but has Bash, so each is told never to run anything that writes): areas from the lanes' `owns`, else the top-level source folders (`.claude/rules/` paths
    only split a big folder: review round 1 found every install's rules cover docs and tests, not
    source); uncovered source is listed as not checked; at most six; the skill on `opus`, the
    area audits on `sonnet`; findings in one shape (severity, check ID, `path:line`,
    why). *Why:* areas keep each audit small and parallel; Sonnet keeps a full audit affordable.

86. **`/code-health` is the whole-codebase audit, not a diff review:** Claude Code's `/code-review`,
    `/simplify` and `/security-review` cover the current change. It judges against the project's own
    rules, writes a dated report, and turns chosen findings into backlog items; its description
    says so. *Why:* the kit must add something over the built-ins (backlog
    `readme-builtins-comparison`).

## 2026-10-06: Plan 07b scope

85. **`/onboard` moves from plan 07b to plan 08; 07b is `/design` and `/code-health`.** *Why:*
    whether the kit ships as a plugin (backlog `ship-kit-as-plugin`) decides what `/onboard` is: a
    plugin can't ship deny rules, `CLAUDE.md` or project-owned files, so on that route `/onboard`
    becomes the project setup step. Its lane proposals also wait on `lane-overlap-check` and
    `lane-resources-env`, and it should use `lane-dependency-hint`'s lockfile table
    (`docs/survey-lanekeeper.md`). Decision 68 moves with it. 07b also tries a lighter process
    (backlog `lighten-plan-process`).
    *Since reconciled with decisions 77–78 on merging main:* for v0.1, plan 08 is the copy
    installer and `/onboard` stays in v0.2, where its plugin-or-installer question is settled.

## 2026-10-06: Lane instructions, checked on Linux

84. **Decision 35 stands on Linux and Windows; no code change.** A live check with Claude Code
    2.1.291, on WSL2 Ubuntu and native Windows, planted a word in each instruction file:
    - A lane never loads the main checkout's *committed* `CLAUDE.md` or `.claude/CLAUDE.md`, even
      with no excludes and with different content in the lane's copy. A plain subfolder in the same
      place does load its parents' files, so this is specific to worktrees. The kit's excludes for
      those files are now redundant, and are kept as a backstop for other Claude Code versions,
      since the docs don't promise this behaviour.
    - A lane does load the main checkout's *personal* `CLAUDE.local.md` (gitignored, so it exists
      only there). The kit doesn't exclude it: personal instructions are meant for every session.
    - An exclude in the **lane's own** `settings.local.json` works on both systems. On Linux, the
      main checkout's `settings.local.json` also applies to every lane, as the settings docs say;
      on Windows it doesn't. The kit only writes to the lane's file, so nothing breaks.

    Not tested: an `AGENTS.md`-only project. Backlog `lane-settings-cross-platform` is done.

## 2026-10-06: Windows CI speed

83. **CI jobs time out after 10 minutes, and Windows CI leaves Defender on.** *Measured in
    `chore/faster-windows-ci`:* with real-time scanning off, the Windows full job took 4m03s
    (pytest 3m34s), against 3m17s–3m54s on main; the time goes to process start-up, not scanning.
    The timeout stops a hung job holding a runner for GitHub's 6-hour default; the slowest job
    takes about 4 minutes.

## 2026-10-05: The v0.1 plan

The owner asked for guidance on how the kit should be built. These were Claude's recommendations,
and the owner accepted them. Research behind them: `docs/survey-claude-code.md`, `docs/survey-lanekeeper.md`.

82. **Permission defaults follow the current docs.** The secrets default becomes `.env.*` with a
    `!.env.example` exemption: a deny rule that starts with `!` is a gitignore negation, and the wider
    pattern also catches `.env.production` and the like. This replaces decision 31's list.
    Decision 30's extra hook block in `bypassPermissions` is removed after one live check, because
    the docs say ask rules prompt in every mode, bypass included. Both are done in the v0.1 fix
    batch (backlog `revisit-permission-decisions`).

81. **The repo and the CLI are renamed to `worklanes` together, at launch (plan 12).** *Why:* one
    rename instead of churn while plans are open. Until then the CLI stays `kit`.

80. **Evals move to v0.2: about five small `claude -p` scenarios.** v0.1 proves usefulness with a
    real two-lane trial instead (backlog `prove-it-on-a-real-project`), which also replaces plan 11's
    example project. *Why:* a trial with real tasks is cheaper and says more about usefulness;
    evals then guard against regressions. `claude plugin eval` can't load a project's `.claude/` or
    `CLAUDE.md`, so plan 11 keeps its own harness and borrows plugin eval's design (repeat runs, a
    baseline, a cost cap).

79. **Lighter process.** At most three open questions per plan. Claude brings each one with a
    recommended answer, and the owner approves or pushes back. Small plans get one review round
    unless it finds a 🔴. *Why:* 74 decisions for about 3,500 lines of code is too much ceremony,
    and it slows delivery (backlog `lighten-plan-process`).

78. **v0.1 installs by copying files (plan 08, one `kit init`); the plugin comes in v0.2.** Keep
    kit-owned files in a layout that can become a plugin's. *Why:* two plugin limits would break
    features that work today. A plugin agent's `hooks` frontmatter is ignored, so the reviewer
    would lose its read-only guard. A plugin's `bin/` is only on the PATH of Claude's Bash tool, so
    pre-commit, CI and people's own terminals couldn't run the checks. Copying files works now and
    is tested; the plugin brings updates and a one-line install once the kit is proven.

77. **v0.1 is a small kit that works, then it grows.** Build only what Claude Code doesn't already
    do: lanes with an enforced task cycle. The order:
    1. plan 07 (done);
    2. a batch of small fixes: lane settings on macOS/Linux, the permission decisions, live checks
       that say what they load, lint and format in CI, the test command in `AGENTS.md`;
    3. the lane-boundary check, with a rule for files two lanes claim;
    4. the installer (plan 08);
    5. a two-lane trial on a small web project;
    6. the CI template (plan 09);
    7. launch (plan 12).

    v0.2 holds the rest: the plugin, plan 07b, the Unity pack, evals, per-lane ports, and most of
    the backlog. *Why:* the project had grown past what one owner can steer, and nothing is proven
    useful until someone other than its author can install it and run two lanes.

## 2026-10-05: Plan 07 questions

76. **A `blocked_by` names a backlog item's slug or a plan's file name (or path);** it is done once
    the item is in `docs/backlog/done/` or the plan in `docs/plans/finished/`. One that names
    neither is reported under Problems and still blocks. *The owner's call at PR review:* the
    backlog README already allowed plans, and a typo would otherwise block an item forever, unseen.

75. **`lanes status` and the lane router count changed and untracked files apart,** like `kit next`
    and `lanes finish`, all through one parser (`lanes.changes`); only changed tracked files are
    called uncommitted work. *The owner's call at PR review:* decision 52 gave "unfinished" one
    meaning, and `/next` reads the `lanes status` block for other lanes.

72. **`docs/design/decisions-log.md` is a default shared path.** *Found in the live run:* the skills
    add decisions there from a lane (ARCHITECTURE §8 allows one entry per task), and the ownership
    hook asked because only `docs/changelog.d/`, `docs/backlog/` and `docs/plans/` were shared.
    Confirmed by the owner at PR review, as were 65 and 71.

71. **Skills run the kit as `sh .claude/kit/kit <command>`,** a kit-owned launcher beside the hook
    launcher that takes Python from `.claude/kit/python-path` and passes exit codes through. *Settled
    during the build, confirmed by the owner at PR review:* a kit-owned skill can hold neither the
    rendered `{{kit_command}}` nor an interpreter path (decision 57's reason), and one fixed command lets
    `allowed-tools` pre-approve exactly `kit next`. It doesn't settle the root shim question (§15,
    plan 08), which is about what humans type.

61. **Plan 07 is split.** 07 = the task loop (`/next`, `/plan-feature`, `/implement`, `/wrap-up`);
    07b = `/design`, `/code-health`, `/onboard`. Later plans keep their numbers. *Why:* seven skills
    don't fit one screen of steps, and `/onboard` writes what the installer (08) sets up.

62. **The skills work outside a lane, with no new CLI.** Outside a lane folder (no `[[lanes]]`, or the
    main checkout) `/plan-feature` makes the task branch with `git switch -c`, and `/wrap-up` commits,
    then proposes the push and `gh pr create` (PR mode) or stops after the commit (local mode). Every
    skill's step 0 says which case it is in. *Why:* `lanes start`/`finish` refuse outside a lane
    (decision 51), and a project without lanes still deserves the loop.

63. **`kit next` gathers the facts; the `/next` skill words them.** Read-only, stdlib, tested: lanes and
    PRs, plan status lines, backlog headers, skipping `README.md`, `_TEMPLATE.md`, `done/`, `finished/`.
    *Why:* rules written only as skill prose can't be tested.

64. **No payload skill shares a name with this repo's own skills;** if Claude Code shows payload skills
    here (nested `.claude/skills/` load when working on files there), this repo's prototype becomes
    `/kit-next`. *Why:* plain `/next` must never mean two things.

65. **`/wrap-up` passes the PR body on stdin: `lanes finish --body-file -`** with a heredoc; the kit
    reads it before the tests run and hands it to `gh` as UTF-8 bytes with LF endings. *Changed
    during the build:* the approved answer was a file in `.claude/kit/tmp/`, but the live run showed
    every write there asks (the kit's own ask rule on `.claude/kit/**`, and the ownership hook for
    any path outside the lane), so a file would prompt on every wrap-up. Stdin needs no file and
    no gitignore entry.

66. **Repeated corrections become one proposed rule, never an unasked one.** `/wrap-up` looks back over
    its session and asks the owner; for each repeat it proposes one of a `.claude/rules/` line (know it
    while writing), a `P` check (catch it in review) or a `kit.toml` pattern (a literal that must never
    appear), and writes it on a yes, in its own commit. *Why:* a skill sees only its own session.

67. **Skills pre-approve only read-only tools; skills that change things are user-invoked only**
    (`disable-model-invocation: true`: `/plan-feature`, `/implement`, `/wrap-up`). Tests hold both.
    *Why:* the owner's yes in chat is followed by a real permission prompt for commits and pushes.

68. *(07b)* **`/onboard` proposes at most three `P` checks,** each tied to something it found, and after
    approval calls `kit settings sync` and `kit lanes create` besides `kit check settings`. (The plan
    draft said `kit check settings` doesn't exist; it does, from plan 03: it reports settings drift.)

69. *(07b)* **`/code-health` writes `docs/health/YYYY-MM-DD.md`** from a template in its own skill folder.

70. **Skill `model` and `effort` fields are kept only if they work:** checked against the docs page and a
    live run before use; otherwise dropped from the skills and §9.

## 2026-10-05: Product name and lanekeeper

74. **Build on lanekeeper rather than reinvent it.** `docs/survey-lanekeeper.md` records what to
    borrow, step by step, at a pinned commit, like `survey-hoem.md` (reference, not spec). Borrowed
    code keeps lanekeeper's MIT notice and names its source file and commit. Ideas and test cases
    are taken freely. *Why:* it solves the same problem and found real bypasses and Windows pitfalls
    the hard way; the owner wants the kit to improve on useful tools, not duplicate them. Where the
    kit's design differs (long-lived lanes, enforcement inside Claude Code, stdlib only), the kit's
    design wins.

73. **The kit's name is `worklanes`** (plugin name, and the name the README and launch use).
    *Why:* `claude plugin validate` reserves names starting with `claude-`, so
    `claude-code-lanes-starter` can't be the plugin name, and a published plugin name can't change.
    `worklanes` was free on PyPI, npm and GitHub (2026-10-05) and says what the kit does. `laneguard`
    was the other finalist, but it means nearly the same as `lanekeeper`, an existing tool for the
    same problem ([kish21/parallel-agents](https://github.com/kish21/parallel-agents)), so the two
    would be confused. Renaming the repo, the `kit` CLI command and the docs is left to plan 08/12
    (backlog `plugin-name`).

## 2026-10-05: Plan 06 questions

54. **Review checklists live in `.claude/review/`**: `universal.md` (kit-owned), `project.md`
    (project-owned) and one `<pack>.md` per pack; the reviewer reads every `*.md` there. *Why:* the
    subagent docs say `.claude/agents/` is scanned recursively, so a checklist beside the agent could
    be read as an agent; and a pack adds checks by dropping in a file, with no registry.

55. **Every check has a stable ID with a per-file prefix** (`U`, `P`, a pack's own), and findings
    cite it. *Why:* a finding traces to the rule it breaks, and rules can be discussed by number.

56. **The reviewer judges only changed lines** of the task's diff (against the merge base with the
    integration branch, plus uncommitted and untracked files), reads the matching path-scoped rules
    itself, and lists at most three pre-existing problems without a severity. It keeps `CLAUDE.md`
    and `AGENTS.md` loaded. *Why:* a review that wanders into old code buries the findings that
    matter; the author and reviewer must judge against the same rules.

57. **The reviewer is read-only by enforcement, not by request:** `tools: Read, Grep, Glob, Bash`,
    and a `PreToolUse` hook in the agent's own frontmatter (`kit hook reviewer-bash`) allows only
    read-only git commands. It fails closed, unlike the other non-guard hooks. It never runs the tests;
    its caller does. *Why:* the docs don't say whether `tools` accepts `Bash(...)` patterns, and a
    reviewer that can run `git checkout` can lose the author's work. The hook runs through a `sh`
    launcher (`.claude/kit/hook`) that reads `.claude/kit/python-path`, because a kit-owned file
    can't hold a machine's interpreter path; any launcher failure exits 2. Allowed besides read-only
    git: `cd <folder>` (agents start with it by habit), and `$`, backticks, `<`, `>` inside single
    quotes (and `<`, `>` inside double quotes), where they are plain text; unquoted globs are refused,
    since bash expands them after the check. Not enforced: `git status` and `git diff` may take the
    author's index lock; the agent is told to use `--no-optional-locks`, and a collision only fails
    the author's next git command. *Found live:* Claude Code
    skips an agent's frontmatter hooks in an untrusted folder (ARCHITECTURE §15).

58. **The report has one fixed shape** (verdict, numbered findings with 🔴/🟠/🟡 from
    `CODE-STANDARDS.md` §6 and a check ID, checks run, outside this change), and an unsettled design
    question is a finding for the owner, never settled by the reviewer. *Why:* `/wrap-up` and people
    read it the same way, and it goes into PR bodies as is.

59. **The reviewer runs on `opus`.** *Why:* it is the one independent check before a human, once per
    task; a missed bug costs more than the tokens.

60. **This repo reviews its plans with its own reviewer from plan 06 on,** using copies of the
    payload's agent and universal checklist that a test keeps identical (except the path to the
    kit). *Why:* dogfooding: every PR after this one shows the kit's reviewer at work.

## 2026-10-05: Plan 05 questions

53. **A merged PR proves a branch merged only if its base is the integration branch.** *Settled during
    the third review:* a stacked PR merged into its parent branch hasn't reached `main`, and `start`
    would otherwise delete the branch.

52. **Only tracked changes block `start`, `sync` and `finish`; untracked files are listed in a note**
    that says the tests see them but they won't land: commit the ones that belong to the task, put
    generated ones in `.gitignore`. *The owner's call during the third review:* test runners leave
    reports (`junit.xml`, `coverage/`), and refusing on them would push an agent to `git add -A` them
    into the branch. The cost, found in the fourth review: a forgotten `git add` is tested but doesn't
    land, so the note says so plainly. git itself still refuses a switch that would overwrite an
    untracked file.

46. **`lanes start` proves the previous task branch merged, or refuses.** Merged means its tip is
    in the integration tip (after a fetch in PR mode), or, in PR mode, `gh` reports a `MERGED` PR
    whose head commit is that tip. A PR found by branch name alone never counts (a reused slug could
    match an old one). Open, closed, no PR at that commit, or no `gh`: refuse with the reason;
    `--abandon` drops the branch on purpose and prints its SHA. Other leftover `<lane>/*` branches
    are listed, never deleted. *Why:* squash merges can't be seen locally, and guessing "merged"
    loses work.

47. **Task branches have no upstream until they are pushed** (`git switch --no-track -c`), and slugs
    follow the lane-name pattern, at most 50 characters. *Why:* git would otherwise track
    `origin/<integration>`, and every "pushed?" check would be wrong.

48. **`lanes sync` rebases a branch that was never pushed and merges one that was; a conflict is
    left in progress** with the files and the continue/abort commands. *Why:* never rewrite
    commits under review (no force-push), and resolving the conflict is the agent's work, not
    something to undo silently.

49. **`lanes finish` = sync → tests → publish.** PR mode pushes and opens the PR with `--title` and
    `--body-file` (defaults: the oldest own commit's subject, a commit list), only pushes when a PR
    is open already, never force-pushes, and exits non-zero with the URL when `gh` can't open it.
    Local mode refuses while the main checkout holds the integration branch, fast-forwards it,
    re-syncs, re-tests and retries once if another lane landed first, then detaches and deletes the
    merged branch. *Why:* the tests must run on what actually lands.

50. **`test_command` runs through the platform shell in the lane folder, with no skip flag.** *Why:*
    real test commands chain (`npm test && ...`); the value comes from the committed, protected
    `kit.toml` (decision 30); "evidence, not claims".

51. **`start`, `sync` and `finish` run only inside a lane folder** and print short lines an agent can
    quote, each step as it happens. Exit 2 means refused with nothing changed; exit 1 means
    unfinished, something is mid-way (tests failed, a conflict waits, a push or PR failed); the plan
    said exit 1 for every failure, settled during review to match the other `kit` commands. *Why:*
    the lane comes from the folder (decision 37), and an agent must be able to tell "nothing
    happened" from "look before going on".

## 2026-10-04: Plan 04 questions

35. **Lanes stay nested; each lane skips the main checkout's instructions.** `lanes create` adds
    `claudeMdExcludes` entries for the main checkout's `CLAUDE.md`, `.claude/CLAUDE.md` and `AGENTS.md` to the lane's own
    `.claude/settings.local.json` (gitignored, specific to one machine; other keys kept). *Why:* Claude Code loads every
    `CLAUDE.md` from the session folder up to the filesystem root, so a nested lane would also read
    the main checkout's copy, which may be stale. If the live check shows the setting doesn't
    work, the default becomes the sibling folder `../{project}-lanes`.

36. **A lane's hooks read the lane's own `kit.toml`; the router warns when the integration branch's
    copy differs.** *Why:* consistent with decision 33; lane definitions change rarely, and a warning
    is enough to make the next task start from the new ones.

37. **A folder is a lane when its git top level is `<main checkout>/<worktree_root>/<name>`.** The
    main checkout is the git top level when run there; from a linked worktree it is git's first
    `worktree list` entry (a submodule's `core.worktree`), and it must have `.claude/kit.toml`
    checked out, which rules out a separate git dir. Any other folder is "not a lane": the router
    says so and ownership doesn't judge it. *Why:* derived from git and the config, so no state
    file can go stale.

38. **The kit never moves the main checkout.** `lanes status` reports what it holds and, in local
    mode, warns when the integration branch is checked out there, with the command to fix it.
    *Why:* never surprise the owner; local mode's fast-forward (plan 05) needs it detached.

39. **`lanes create` works offline and refuses unsafe layouts.** It creates from the integration
    tip: `origin/<integration>` in PR mode, the local branch in local mode (where work lands), each
    falling back to the other; the router and `status` measure against the same ref. It refuses a nested
    `worktree_root` that isn't gitignored, and any existing folder that isn't already that lane's
    worktree. It copies `.worktreeinclude` files that are also gitignored, matched by git itself.
    *Why:* Claude Code honours `.worktreeinclude` only for worktrees it creates itself, and the
    installer rule (never edit a user's file unasked) applies to `.gitignore` too.

40. **The lane router uses local git data only, never blocks, and tells the agent when it fails.**
    It warns on: detached HEAD (between tasks), a branch outside `<lane>/`, behind the integration
    tip, already merged, uncommitted changes, and `kit.toml` drift. *Why:* SessionStart can't block
    anyway, and a silent failure would look like "all clear".

41. **Ownership is a separate PreToolUse hook that asks and fails open.** Edit, Write, MultiEdit and
    NotebookEdit outside `owns` + `shared_paths` → `permissionDecision: "ask"` with the reason. Bash
    writes aren't checked. *Why:* ownership reduces conflicts, it isn't security (unlike decision 33).

42. **`[[lanes]]` is validated strictly.** Names match `^[a-z0-9][a-z0-9-]*$` (they are folder
    names and branch prefixes). Names are unique and none equals the integration branch. `owns`
    is required and non-empty; overlaps are allowed and reported as a note. *Why:* decision 24; a
    bad name would only fail later, inside git.

43. **`lanes status` shows PR state when `gh` is available, "unknown" otherwise**, never failing,
    with `--offline` to skip it. *Why:* status must work offline and without `gh`; head-commit
    matching stays with plan 05.

44. **From a lane, edits to the main checkout or another lane's folder ask too.** *Settled during
    review; confirmed by the owner with PR #6:* the plan said "outside the project → allowed", but
    an agent writing to the main checkout by absolute path is exactly the cross-lane conflict
    ownership exists to catch. Paths outside the repository are still not judged.

45. **`lanes remove` refuses when ignored files hold work** (`.env`, changed local settings, build
    output), listing them; `--force` deletes anyway. Not counted: files and folders identical to the
    main checkout's *current* copy (what `create` copied in), the `claudeMdExcludes` it added, and
    caches tools rebuild (`__pycache__`, `.pytest_cache`, `node_modules`, `.venv`...; counting them
    would make `--force` routine). *Why:* git doesn't count ignored files as changes, so
    `git worktree remove` would delete them without a word.

## 2026-10-04: Plan 03 questions

27. **The protected-paths hook watches more than commands.** `Bash|PowerShell` commands against
    `[protected].commands`; `Edit|Write|NotebookEdit` paths against `[protected].paths` (still
    protects when `settings.json` drifts); and, best effort, the targets of common PowerShell write
    cmdlets, Bash file commands (`rm`, `mv`, `cp`...) and output redirections. *Why:* native Windows has no sandbox, and Claude Code doesn't
    document whether deny rules cover PowerShell writes.

28. **Command matching stays simple.** Split compound commands, strip assignments, wrappers and git
    global options, then match program and subcommand with the remaining flags in any order (short
    flag clusters expanded). `bash -c` strings, aliases, `+refspec` pushes and scripts are documented
    misses. *Why:* the hook guards against mistakes, not adversaries (decision 15); cleverness past
    the cheap cases is maintenance without a guarantee.

29. **`kit settings sync` only adds rules and removes rules it wrote**, recorded in
    `.claude/kit/generated-rules.json`. Owner rules are never touched; `kit check settings` reports
    missing and stale rules. *Why:* `settings.json` has no comments to mark ownership, and a marker
    key could trip Claude Code's settings validation. Plan 08 may fold the record into its manifest.

30. **The kit's own config gets ask rules, plus a hook block only in `bypassPermissions`.**
    `settings.json`, `kit.toml`, `.claude/kit/**`, `.githooks/**`; `[protected] guard_kit = false`
    turns both off. *Why:* `/onboard` must be able to write `kit.toml` with the owner's approval, but
    ask rules don't prompt in bypass mode, where nobody is watching.
    *Superseded in part by decision 92:* they do prompt there, so the hook block is gone.

31. **`[protected].secrets` → `Read` and `Edit` deny rules**, default `.env`, `.env.local`,
    `.env.*.local`. *Why:* an allow can't carve an exception out of a deny, so `.env.*` would block the
    committed `.env.example`.
    *Superseded by decisions 82 and 92:* a `!` exemption can.

32. **`kit check protected` reports changes to protected paths; `KIT_ALLOW_PROTECTED=1` lets a human
    commit them.** How a PR declares an intended change (label, trailer, `CODEOWNERS`) is plan 09's.
    *Why:* intended changes happen; the escape must be explicit and visible.

33. **The hook finds the project from the call's `cwd`; a missing `kit.toml` allows, anything broken
    blocks** (exit 2: in PreToolUse, exit 1 and timeouts let the call through). *Why:* decision 9, made
    true against the real hook protocol; a lane uses its own worktree's config.

34. **The agent can't switch the local checks off.** Default commands include `git commit
    --no-verify` / `-n`; the hook blocks commands that set `KIT_ALLOW_PROTECTED` or change
    `core.hooksPath`. The docs say CI (and branch protection, plan 09) is the gate. *Why:* a guard the
    guarded party can disable is a suggestion.

## 2026-10-04: The repo's own `/next`

26. **This repo gets its own `/next` skill now, as a prototype for plan 07's installable one.** It
    reads the branch, open PRs and CI, the plans index and plan statuses, and ARCHITECTURE §15; it
    prints where the build stands and **one recommended prompt**, and is told to change nothing.
    `allowed-tools` only pre-approves tools (anything else would prompt), so its grants are kept to
    read-only commands, exact where a wildcard could match a writing form such as `git branch -D`;
    `tests/test_repo_skills.py` enforces the list. It also reports docs that
    disagree, without fixing them. *Why:* the owner wants a fresh session to know where things
    stand in one command; building the simple version first gives plan 07 real usage to learn
    from. The installable version (lanes, backlog files) stays in plan 07.

## 2026-10-04: Plan 02 questions

23. **Comment stripping is simple and errs towards missing, never false alarms.** Line comments by
    file type plus block comments; no string parsing, so a comment marker inside a string ends
    checking for that line. Rules can set `ignore_comments = false`. *Why:* a check that cries wolf
    gets disabled; a rare miss is still caught in review.

24. **Unknown keys in `kit.toml` are errors.** On the CLI and in CI they fail the run; in hook mode
    they are a visible, non-blocking hook error (fail open, decision 9). *Why:* a typo such as
    `pathes =` must not silently switch a rule off.

25. **Pre-commit is git's own hook mechanism** (`.githooks/pre-commit`, POSIX sh, which Git for
    Windows also runs), enabled by the installer through `core.hooksPath` only after asking. The
    pre-commit framework is a Later option. *Why:* no extra dependency, works the same everywhere.

## 2026-10-04: Plan 01 questions

21. **No `BUILD-STATE.md` in the MVP templates.** It arrives with the `/sync-state` skill that keeps
    it true. *Why:* a status doc nothing maintains goes stale, and a stale status doc misleads agents.

22. **Every project gets `docs/design/decisions-log.md`; `VISION.md` and `DESIGN.md` ship as short
    stubs marked "delete if you don't need this".** *Why:* every project makes decisions worth a
    why, but a small library may never need a vision document.

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

13. **No shared append-only files.** Changelog entries are fragments (`docs/changelog.d/`)
    compiled at release. Backlog items are one file each (`docs/backlog/<slug>.md` with a small header:
    status, lane, size), like plans already are. `BUILD-STATE.md` is regenerated, never hand-merged.
    *Why:* every lane's wrap-up edited the same files, the main source of merge conflicts.
    Fragments (the towncrier/changesets pattern) make those conflicts impossible; `merge=union` was
    considered and rejected as fragile. Fragments are named `<lane>-<task>.md`, because branch
    names contain `/`.

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
   *Revised in plan 00:* one file, `.claude/kit.toml`, holds lanes, checks and protected paths.

9. **Fail modes differ per hook.** The rules-check hook fails *open* (a crash never blocks an edit).
   The protected-paths hook fails *closed* (a broken config blocks with a clear message), because a
   guard that silently switches off is worse than a noisy one.
