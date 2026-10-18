---
status: idea
lane: any
size: S
---
# Keep the installer from crashing on characters its console can't print

On Windows, when the installer's output is piped (`| tee`, CI, a script capturing it), Python
writes in the console code page (cp1252), so a target folder, or now an answer such as an origin
default branch, with a character outside it crashes with `UnicodeEncodeError` before anything is
written (`installer/main.py`, the "Installing parallanes into" line). The kit's own CLI already
reconfigures its output (`payload/kit-owned/.claude/kit/cli.py`); the installer doesn't. Found in
`installer-dry-run-prompts` review round 1; it predates that change.

**Done when:** a piped install into a folder named with non-cp1252 characters runs to the end on
Windows, tested.
