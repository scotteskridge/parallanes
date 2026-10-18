---
status: idea
lane: any
size: S
---
# Catch the rest of PowerShell's ways to set a `KIT_ALLOW_*` variable

The allow-variable check (`kitlib/commands.py`, `_sets_allow_variable`) judges only the first word
of a command as the assignment target. Real PowerShell sets the variable with each of these, and
the hook lets them through (found by `allow-variable-braced-powershell`'s review round 1; all
predate it):

- `$env:KIT_ALLOW_PROTECTED++`, `++$env:KIT_ALLOW_PROTECTED` (null + 1 is 1)
- `$a = $env:KIT_ALLOW_PROTECTED = 1`, `$env:KIT_ALLOW_PROTECTED, $b = 1, 2`
- `[string]$env:KIT_ALLOW_PROTECTED = 1`
- `Set-Content env:KIT_ALLOW_PROTECTED 1`, `sc env:...`, `Copy-Item env:COMSPEC env:KIT_ALLOW_PROTECTED`
- `${env:\KIT_ALLOW_PROTECTED}=1`, `${Microsoft.PowerShell.Core\Environment::KIT_ALLOW_PROTECTED}=1`

They're listed under "Known misses" in `docs/ai/protected-paths.md`. Mistakes are what the guard
is for (the module docstring), and none of these is a likely mistake, so this is polish.

**Done when:** each form above is caught for both variables, quoting them in prose still passes,
and the known-misses line is removed; tests in `tests/test_commands.py`.
