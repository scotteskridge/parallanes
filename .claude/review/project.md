# Project checks (prefix P)

Checks for the kit repo itself, beside the kit's `universal.md` (a copy of the payload's; a test
keeps them equal).

P1. **Stdlib only where it's installed.** Nothing under `payload/` or `packs/` imports a package
    outside Python 3.11's standard library. Dev-only tools (pytest) stay in `tests/`.
P2. **Windows first.** Paths with spaces and backslashes are tested; files the kit writes use LF
    explicitly; shell commands work in Git Bash and, where documented, PowerShell.
P3. **Hook failure policy.** A new or changed hook states whether it fails open or closed, and why
    (`kitlib/hooks.py` docstring, decisions log); in PreToolUse only exit 2 blocks, so a hook that
    must block exits 2 on every error path, with a test for each.
P4. **Never overwrite the user's files.** Installer and CLI code that writes into a project asks
    before replacing a file it didn't create.
P5. **The trail.** The plan's *Notes after implementation*, the decisions log, ARCHITECTURE §15 and
    the CHANGELOG match what the code now does.
