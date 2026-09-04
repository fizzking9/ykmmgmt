"""Make the mcp_server package importable regardless of pytest's rootdir."""

import sys
from pathlib import Path

PACKAGE_PARENT = str(Path(__file__).resolve().parents[2])
if PACKAGE_PARENT not in sys.path:
    sys.path.insert(0, PACKAGE_PARENT)
