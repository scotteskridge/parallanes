---
status: next
lane: any
size: S
---
# Catch `${env:KIT_ALLOW_*} = 1` in PowerShell

The protected hook blocks an agent setting `KIT_ALLOW_PROTECTED` or `KIT_ALLOW_CROSS_LANE`
(`kitlib/commands.py`, `_sets_allow_variable`), but PowerShell's braced form
`${env:KIT_ALLOW_PROTECTED} = 1` isn't caught: the first word doesn't start with `$env:`. Found by
the lane-boundary check's review (decision 96).

**Done when:** the braced form (with and without spaces, any case) is caught for both variables,
and quoting it in prose still passes; tests in `tests/test_commands.py`.
