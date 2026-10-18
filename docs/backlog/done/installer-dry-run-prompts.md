---
status: next
lane: any
size: S
---
# Make the installer's dry run show its answers without asking

`install.sh --dry-run` still asks the setup questions, so a scripted dry run stops with "no answer
(input closed)" unless `--yes` is added. With `--yes` it lists the files but not the answers it took
(project name, stack, test command), which are what a person most wants to check before installing
(two-lane trial, F1).

**Done when:** a dry run with no input open takes the detected defaults and prints them with the
file plan, and a test covers a dry run with stdin closed.
