#!/bin/sh
# Install the kit into a project (plan 08): find Python 3.11+, check git, then run kit_setup.py.
# Usage: sh install.sh [--target DIR] [--dry-run] [--yes]
# Only shell built-ins run before Python is found, so a bare PATH still gets a clear message.

case "$0" in
    */*) here=${0%/*} ;;
    *) here=. ;;
esac

# The first that runs as 3.11+ wins. Running each one matters: on Windows (Git Bash) `python` may be
# the Microsoft Store alias, which exits without running anything (decision 19).
python=""
for name in python3 python python3.13 python3.12 python3.11; do
    candidate=$(command -v "$name") || continue
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
        python=$candidate
        break
    fi
done
if [ -z "$python" ]; then
    echo "install.sh: the kit needs Python 3.11 or newer as python3 or python on PATH: https://www.python.org/downloads/" >&2
    exit 1
fi

if ! command -v git >/dev/null 2>&1; then
    echo "install.sh: the kit needs git: https://git-scm.com/downloads" >&2
    exit 1
fi
if ! command -v claude >/dev/null 2>&1; then
    echo "install.sh: Claude Code isn't on PATH; install it before opening the project: https://code.claude.com/docs" >&2
fi
if ! command -v gh >/dev/null 2>&1; then
    echo "install.sh: GitHub CLI (gh) not found: optional, needed only for lanes in pull-request mode" >&2
fi

exec "$python" "$here/kit_setup.py" "$@"
