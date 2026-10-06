# Install the kit into a project (plan 08): find a real Python 3.11+, check git and sh, then run
# kit_setup.py with the same arguments.
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1 [--target DIR] [--dry-run] [--yes]

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# `python` may be the Microsoft Store alias, which doesn't run Python (decision 19). Each candidate
# is run, and the alias fails the probe. No path is skipped: python.org's install manager and Store
# Python put working interpreters under WindowsApps too. The candidate prints its own
# sys.executable, so the `py` launcher resolves to the real interpreter it picked.
$probe = 'import sys; print(sys.executable) if sys.version_info >= (3, 11) else sys.exit(1)'
$python = $null
foreach ($candidate in @(@('py', '-3'), @('python'), @('python3'))) {
    $commands = Get-Command $candidate[0] -All -CommandType Application -ErrorAction SilentlyContinue
    foreach ($command in $commands) {
        $extra = @($candidate | Select-Object -Skip 1)
        try {
            $found = & $command.Source @extra -c $probe 2>$null
        } catch {
            continue
        }
        if ($LASTEXITCODE -eq 0 -and $found) {
            $python = ($found | Select-Object -First 1).Trim()
            break
        }
    }
    if ($python) { break }
}
if (-not $python) {
    [Console]::Error.WriteLine('install.ps1: the kit needs Python 3.11 or newer as py, python or python3 on PATH: https://www.python.org/downloads/')
    exit 1
}

$git = Get-Command git -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $git) {
    [Console]::Error.WriteLine('install.ps1: the kit needs Git for Windows: https://git-scm.com/download/win')
    exit 1
}
# The hooks and the kit command run through sh (decision 99); Git for Windows ships it in bin\.
$sh = Get-Command sh -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $sh) {
    $sh = Join-Path (Split-Path -Parent (Split-Path -Parent $git.Source)) 'bin\sh.exe'
    if (-not (Test-Path $sh)) {
        [Console]::Error.WriteLine("install.ps1: the kit needs Git for Windows' sh (Git Bash); reinstall Git for Windows")
        exit 1
    }
}
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    [Console]::Error.WriteLine("install.ps1: Claude Code isn't on PATH; install it before opening the project: https://code.claude.com/docs")
}
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    [Console]::Error.WriteLine('install.ps1: GitHub CLI (gh) not found: optional, needed only for lanes in pull-request mode')
}

# Windows PowerShell 5.1 passes 'D:\my proj\' (tab completion adds the backslash) as "D:\my proj\",
# which Python reads as D:\my proj" : drop a trailing backslash from an argument with a space.
$passed = @($args | ForEach-Object { if ($_ -match ' ' -and $_ -match '\\$') { $_.TrimEnd('\') } else { $_ } })
& $python (Join-Path $here 'kit_setup.py') @passed
exit $LASTEXITCODE
