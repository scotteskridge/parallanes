---
status: later
lane: any
size: S
---
# Show `kit check` results on the pull request page

In CI a failed check is a red X, then a click, then a log to scroll. lanekeeper writes its verdict
as markdown to `$GITHUB_STEP_SUMMARY` (a pass gets a line too, so a reviewer can see the check ran)
and prints `::error file=<path>::<message>` lines, so each finding shows on the PR's Files tab.
Details and the escaping rules: `docs/survey-lanekeeper.md`, row `ci-check-annotations`.

**Done when:** `kit check --github` writes the summary and one annotation per finding that names a
file, for every check; plan 09's CI template uses it; tests cover the escaping of `%`, CR and LF.
