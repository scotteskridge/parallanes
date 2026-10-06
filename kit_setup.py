"""Install the kit into a project. Usually run through install.ps1 or install.sh; see installer/main.py."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The installer reuses the kit's own library (rendering, settings sync) straight from the payload.
sys.path[:0] = [str(HERE), str(HERE / "payload" / "kit-owned" / ".claude" / "kit")]

from installer.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
