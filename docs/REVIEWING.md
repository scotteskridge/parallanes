# Reviewing parallanes

Thank you for reviewing. This page tells you what to read, in what order, and what to look for, so
an hour or two goes to the parts that matter. The README explains what the kit does; this page
assumes you've skimmed it.

## The ask

The whole repo has about 16,000 lines of Python, two thirds of it tests. **Please review the
core, about 3,000 lines** (the reading order below): the code that decides whether an agent's edit
is allowed and whether a task may land. Short on time? Steps 4, 6 and 8 hold the main promises.
Everything else (installer, `/next` facts, changelog, templates) is welcome but optional.

Most useful to hear, in order:

1. **Correctness:** a way past a guardrail, a git state the task cycle gets wrong, a crash.
2. **Design:** something that will hurt when the kit grows, or that a simpler shape would do.
3. **Readability:** code you had to read twice. Say where; the author is newer to code review
   than to the problem, and this feedback is wanted.

Severity labels help: **fix now** (wrong or unsafe), **fix soon** (will bite), **polish**.
Leave findings as a GitHub issue or as comments on a PR, whichever you prefer.

## Set up (5 minutes)

You need git and Python 3.11+. On Windows, Git Bash provides the `sh` some tests use.

```bash
git clone https://github.com/scotteskridge/parallanes
cd parallanes
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest -m "not slow"
```

On macOS/Linux use `python3` and `.venv/bin/python`. The fast set takes a minute or two; the full
suite (`-m pytest`) runs real git repos and installs, and takes several minutes. CI runs on
Windows and Ubuntu with Python 3.11 and 3.13.

To see the kit working end to end without installing it, the
[two-lane trial](trial/two-lane-trial.md) and its repository
([parallanes-trial](https://github.com/scotteskridge/parallanes-trial)) show two agents landing
six tasks.

## Three things that make the code easier to read

- **`payload/kit-owned/` mirrors the installed project.** `payload/kit-owned/.claude/kit/cli.py`
  is installed as `.claude/kit/cli.py` in a user's project. `payload/templates/*.tmpl` are filled
  in once by the installer and then belong to the user. `installer/` is the installer itself.
- **Installed code is standard library only** (Python 3.11+, `tomllib`), because it runs in other
  people's projects before anything else is installed. pytest and ruff are dev-only.
- **"Decision 33" in a comment points to `docs/decisions-log.md`,** entry 33, which says why.
  Search the log for `33.` to find it. Making these comments self-contained is on the backlog
  (see *Known gaps*).

## Reading order for the core

All paths are under `payload/kit-owned/.claude/kit/` unless they start with `installer/` or `tests/`.

| # | File | Lines | What it does | What to look for |
| --- | --- | --- | --- | --- |
| 1 | `cli.py` (top 80 lines) | 419 | Entry point; maps results to exit codes | The exit-code contract in the docstring: CLI 0/1/2; hooks 0/2, with 1 meaning "kit error, don't block". The import guard at the top exists so the two guard hooks still fail closed on an old Python |
| 2 | `kitlib/config.py` | 446 | Finds the project root, loads and validates `kit.toml` | Does every bad config fail loudly, with a message a person can act on? |
| 3 | `kitlib/globs.py` | 109 | Gitignore-style matching, the same on Windows and POSIX | Path normalisation: backslashes, case, `..`, paths with spaces |
| 4 | `kitlib/lane_hooks.py` | 203 | The session briefing and the per-edit ownership decision | Ways an edit lands outside the lane without a prompt: other lanes' folders, the main checkout, symlinks, relative paths |
| 5 | `kitlib/lane_owners.py`, `kitlib/lane_boundary.py` | 256 | Who owns a file when patterns overlap; the pre-commit and CI lane check | Do the hook and the check always agree on which lane owns a file? |
| 6 | `kitlib/protected.py`, `kitlib/hooks.py` | 428 | Protected paths, secrets, forbidden commands; the hook entry points and each hook's failure policy | **Fail-open vs fail-closed:** most hooks fail open (a kit bug must not stop the user's work). The two PreToolUse guards, `protected` and `reviewer-bash`, fail closed. Any path where one of those exits 0 or 1 on an error is a bug, except a project with no `kit.toml`, where there's nothing to enforce (decision 33) |
| 7 | `kitlib/commands.py`, `kitlib/file_commands.py` | 571 | Reads shell commands well enough to catch protected ones | Best effort by design (decisions 27, 28), backed by `settings.json` deny rules and pre-commit. A bypass found here is still worth reporting: say which layer would or wouldn't catch it |
| 8 | `kitlib/lane_cycle.py`, `kitlib/lane_merged.py` | 531 | `lanes start / sync / finish` | The central promise: **the suite runs on the exact commit that lands.** Look for a window where `main` moves between the test and the push or fast-forward, and for git states (detached HEAD, dirty tree, branch already merged, rebase conflict) that leave the lane stuck |

Tests are in `tests/`, named after the file or the command (`test_lane_owners.py`,
`test_lane_finish.py`, `test_hook_protected.py`, …). They're the quickest way to see the intended
behaviour.

## Optional areas

- **Installer** (`installer/plan.py`, `installer/main.py`): the rule is "never overwrite a user's
  file". Its bugs have hidden in *re-runs*, so test installing twice.
- **Skills and the reviewer agent** (`payload/kit-owned/.claude/skills/`, `.claude/agents/`): these are prompts,
  not code. A review of whether they're clear and short enough is welcome.
- **Settings generation** (`kitlib/settings.py`): permission rules generated from `kit.toml`.

## Known gaps (no need to report)

These are already on the backlog (`docs/backlog/`) or written down as limits:

- Type hints are incomplete, and CI doesn't run a type checker (`complete-type-hints`,
  `type-check-in-ci`).
- Comments cite decision numbers instead of saying the reason in place
  (`self-contained-decision-comments`).
- Five files are past the project's ~300-line guideline: `config.py`, `cli.py`, `lane_cycle.py`,
  `lane_setup.py` and `commands.py`.
- Changing a file no lane owns, such as `.gitignore` or `package.json`, is still awkward from a
  lane (`shared-path-modes`).
- When the kit's code can't load, the two guard hooks block every tool call, including the edit
  that would fix it, and the message blames the Python version even when a file is broken
  (`kit-load-error-message`).
- What the guardrails can't stop is listed in each project's `docs/ai/protected-paths.md`
  (template: `payload/templates/docs/ai/protected-paths.md.tmpl`). Agents with shell access can
  always do more than a hook can see; the layers are there so no single one is the only check.

## If you have more time

- `docs/ARCHITECTURE.md` is the design every plan builds against.
- `docs/plans/` has one file per piece of work, each with its review findings and fixes.
- `docs/decisions-log.md` records why things are the way they are, newest first.
