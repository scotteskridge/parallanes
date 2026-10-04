"""Make the shipped kit code importable: tests run against payload/, the code that gets installed."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT_CODE = ROOT / "payload" / "kit-owned" / ".claude" / "kit"

if str(KIT_CODE) not in sys.path:
    sys.path.insert(0, str(KIT_CODE))
