"""Make the mcp_server package importable regardless of pytest's rootdir."""

import sys
from pathlib import Path

import pytest

PACKAGE_PARENT = str(Path(__file__).resolve().parents[2])
if PACKAGE_PARENT not in sys.path:
    sys.path.insert(0, PACKAGE_PARENT)


@pytest.fixture(autouse=True)
def _file_store(tmp_path):
    """Isolated per-test file store (same secret as the HTTP test settings)."""
    from mcp_server.files import FileStore, set_default_store

    set_default_store(FileStore(tmp_path / "files", "test-api-key", 3600))
