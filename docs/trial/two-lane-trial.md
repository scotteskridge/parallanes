# Two-lane trial: reading-list app

Backlog `prove-it-on-a-real-project` (build order step 5, decision 98). A small web project with two
lanes, each taking three real tasks through `lanes start` → work → `/wrap-up` → `lanes finish`.

## In short

Two agents built a small web app at the same time, each in its own lane, through six tasks. Every
task landed on `main` in a straight line. Every finish ran the whole suite on the exact commit that
would land: 77 tests at the end. Three times the other lane had landed first, and the kit rebased
onto its work before testing. That sync surfaced the one real conflict (both lanes adding to the
shared decisions log) inside the lane, before `main` moved. When a task needed a file no lane owns,
three things stopped it: the agent asked first, the ownership hook stopped the edit, and pre-commit
refused the commit. Plain worktrees have nothing like the hook or the pre-commit check. Here, the
owner *wanted* the edit, and it still didn't land, so the same three stops are also the trial's
biggest friction (F8). In four of the six tasks the reviewer found a real bug, all fixed before
landing.

The biggest gaps found:
- **F4:** lanes inside the project silently run the main checkout's `node_modules`.
- **F8:** an out-of-lane edit the owner has approved has no smooth way through.
- **F12:** every lane prepends to the same decisions log.

All three are now backlog items.

## Setup (2026-10-07)

- **Project:** `D:\1 office\worklanes-trial` (a path with a space; Windows 10, Git Bash `sh`,
  Node 21, and Python 3.14 picked by the installer). An Express 5 API in `server/`, plain HTML/JS
  in `public/`, tests with `node --test`. GitHub was down, so a local bare repo stood in for it and
  the lanes used `merge_mode = "local"`.
- **Kit:** installed from `main` at 454cf0d with `sh install.sh --target … --yes`. It detected
  Node.js and `npm test` correctly. It didn't include the fixes in PRs 30 and 31, which weren't
  merged yet.
- **Lanes:** `api` owns `server/**` with dev port 3001; `web` owns `public/**` with dev port 3002.
- **How the lanes ran:** `claude -p` sessions in each lane folder, run in parallel, with
  `--permission-mode acceptEdits` and Bash limited to `npm`, `node`, `git` and the kit CLI. The
  driving session played the owner: it answered each agent's questions, took the agent's
  recommendation where it gave one, and ran the browser checks on each lane's own port.
- **Caveats:**
  - The planned interactive task by the owner didn't happen. The owner's part was the decisions
    and the out-of-lane choice.
  - Whether the owner accepted the trial folder's trust dialog wasn't confirmed. If not, the
    reviewer ran without its read-only guard; its reports show no edits.
  - In a background session, the hook's "ask" acts as a refusal. Interactively it is a prompt.

## Tasks

| Lane | Task | Start → finish | Result |
| --- | --- | --- | --- |
| web | book-cards | start → build (75 s) → `/wrap-up` (🟠: no changelog fragment, a process miss rather than a bug; 2 🟡 on test coverage; all fixed) → finish | Landed first: b1f9f2b, 5 tests |
| api | add-book | start → test-first (53 s) → `/wrap-up` (🟠: malformed JSON got an HTML error page; owner chose a JSON 400) → finish | finish rebased onto web's commit and ran all 13 tests on the exact result: cfddb8a |
| api | mark-read | start → test-first (48 s) → `/wrap-up` (2 🟡 fixed; logged 2 owner choices) → finish | b1c1113, 24 tests |
| web | add-form | start (from cfddb8a, so it already had api's new endpoint) → build → browser check on port 3002 → `/wrap-up` (2 rounds; 🟠: submitting before the list loaded reloaded the page) → finish (rebased onto b1c1113) | 0c01d14, 36 tests |
| web | read-toggle | start → test-first with its own plan → browser check → `/wrap-up` (3 rounds; 🟠: a redraw during a save showed a stale checkbox) → finish | e176d3e, 61 tests. Proposed a rule (F11) |
| api | persist | start → plan + test-first → C1, C2 → `/wrap-up` (🟠: a failed save let a retry duplicate a book) → C3 → owner dropped the `.gitignore` change → finish (rebased onto two web commits; C4) | 8333781, 77 tests |

Each task took three or four prompts: the task, `/wrap-up`, and the owner's answers and "yes". A
build step took 1 to 4 minutes, and a review with its fixes took 1 to 6 minutes. Cost per task was
about $1.50 to $4, with the review rounds the largest part.

## What the kit caught

| # | Task | Caught by | What it stopped |
| --- | --- | --- | --- |
| C1 | api/persist | The agent following the lane note (not enforced) | Without being prompted, the agent saw that `.gitignore` is outside `server/**` and asked the owner instead of editing it. |
| C2 | api/persist | Ownership hook | Told to edit it anyway, the agent tried, and the hook asked ("no lane owns .gitignore… allow only if this lane should change it"), which in a background session is a refusal. |
| C3 | api/persist | Pre-commit lane check | With the owner's hand-added lines staged, the commit was refused: `.gitignore: [lanes] outside lane 'api': no lane owns it`. The agent refused to set `KIT_ALLOW_CROSS_LANE=1` itself. The driving session then did set it, and Claude Code's own safety check stopped that commit landing. The owner dropped the change. |
| C4 | api/persist | `lanes finish` sync | Both lanes had added entries at the top of the shared `docs/design/decisions-log.md`. The rebase surfaced the conflict in the lane, before `main` moved, and the full suite ran on the result. The agent's hand merge kept all three entries but put the newest one third, breaking the log's newest-first order (F12). |

C2 and C3 are what plain worktrees lack: they stop an edit to a file no lane owns unless a person
approves it (the hook) or sets the bypass (pre-commit). C1 is the model following the lane note,
which plain worktrees could have too. The price showed here: the edit *was* approved and still
didn't land, so once the server runs, `data/books.json` would be untracked and not ignored on the
trial's `main` (F8). Without the kit's sync, C4 would have surfaced at merge time instead of inside
the lane.

## Friction found

| # | Where | What happened | Becomes |
| --- | --- | --- | --- |
| F1 | install | `--dry-run` without `--yes` still asks the setup questions, so a scripted dry run stops with "no answer (input closed)". It also doesn't show the answers it would take. | [installer-dry-run-prompts](../backlog/installer-dry-run-prompts.md) |
| F2 | install → lanes | In local mode the main checkout must be detached, but only `lanes status` says so. | [local-mode-setup-hints](../backlog/done/local-mode-setup-hints.md) (done, decision 112) |
| F3 | lanes create | New lanes have no `node_modules`, and nothing says so. | [lane-dependency-hint](../backlog/done/lane-dependency-hint.md) (done, decision 103) |
| F4 | lanes (Node) | Worse than F3: no agent noticed, because Node resolves packages up the folder tree and lanes sit inside the main checkout. Every lane silently ran the main checkout's `node_modules`, so a lane that changes a dependency would test the old version and pass. | [lane-dependency-hint](../backlog/done/lane-dependency-hint.md) (done, decision 103) |
| F5 | prompts | "finish it with /wrap-up" inside a prompt can't run it. The skills are `disable-model-invocation`, so a task takes two prompts. | [lane-guide-trial-notes](../backlog/done/lane-guide-trial-notes.md) |
| F6 | lane config | `web` owns only `public/**`, so its tests went into `public/`, where Express serves them. | [lane-guide-trial-notes](../backlog/done/lane-guide-trial-notes.md) |
| F7 | skills in a lane | An agent tried to read the main checkout's copy of a skill, and Claude Code refused (outside the working folder). Cause found: see ARCHITECTURE §15. | [lane-guide-trial-notes](../backlog/done/lane-guide-trial-notes.md) |
| F8 | ownership | An out-of-lane edit the owner approved was stopped three times (C1–C3). The documented bypass, a hand commit with `KIT_ALLOW_CROSS_LANE=1`, was tried by the driving session, and Claude Code's own safety check blocked landing it, so the change was dropped. Repo-wide files (`.gitignore`, `package.json`) will come up in every web project. | [ownership-fix-hint](../backlog/done/ownership-fix-hint.md) (raised to `next`), with [shared-path-modes](../backlog/shared-path-modes.md) |
| F9 | lanes status | In local mode the status line still says `PR: unknown`. | [local-mode-setup-hints](../backlog/done/local-mode-setup-hints.md) (done, decision 112) |
| F10 | trial harness | Not the kit: the background-session allowlist refused `cat`, `curl` and background servers, so the agents couldn't smoke-test in a browser. | cut |
| F11 | /wrap-up rules | The rule-proposal step worked: the same kind of bug came up twice, and the agent proposed a scoped front-end rule. But writing `.claude/rules/` needs a second approval, and no lane owns that folder (F8 again). | [ownership-fix-hint](../backlog/done/ownership-fix-hint.md) |
| F12 | shared docs | Every lane prepends to `docs/design/decisions-log.md`, so two lanes that both decide something conflict (C4). The hand merge broke newest-first order, and `web/read-toggle` added two entries against ARCHITECTURE §8's one-per-task rule, which nothing checks. | [decision-log-fragments](../backlog/decision-log-fragments.md) |

What worked without friction:
- The lane-router told each agent its lane, its paths and its port.
- `lanes start` always began from the latest `main`, so the web lane picked up the API's new
  endpoint with no extra step.
- `lanes finish` ran the tests on the combined result every time.
- The reviewer's 🟠 findings were real bugs, not style notes, apart from one missing changelog
  fragment.
