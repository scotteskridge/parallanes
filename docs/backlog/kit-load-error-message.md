---
status: next
lane: any
size: S
---
# Name the broken file when the kit can't load

When an import fails, `cli.py`'s `import_failure` always says "It needs Python 3.11 or newer; this
is 3.12.2", even when the Python is fine and a kit file is broken. On 2026-10-08 a session left
raw control characters (a null byte among them) in an uncommitted `lane_owners.py`. The protected
hook failed closed, as designed (decision 33), and blocked every Edit, Bash and PowerShell call in
every session, including the edit that would have fixed the file. Its message pointed at the
Python version, so the cause took a while to find, and the owner had to fix the file by hand.

Keep failing closed. Change the message:
- name the file and line that failed (a `SyntaxError` carries both);
- mention the Python version only when it really is older than 3.11;
- say the agent can't fix this itself (its edits are blocked too), and the user has to fix the
  file in an editor or restore it with git.

**Done when:** a broken kit file and an old Python each give their own message, with tests for
both, and the protected hook still exits 2 on each.
