"""Pytest fixtures shared across all backend tests."""

import pytest

from app.core.database import engine


@pytest.fixture
async def _dispose_engine_after_test():
    """Dispose async engine pool after async tests to prevent cross-loop leakage.

    Without this, asyncpg connections created in one function-scoped event
    loop become stale/corrupted when pytest-asyncio creates a fresh event
    loop for the next test, causing "another operation is in progress".

    This fixture is opt-in — only async DB tests request it via
    ``pytest.mark.usefixtures``.  Sync tests skip it entirely so they
    don't pay the cost of creating a throwaway event loop.
    """
    yield
    await engine.dispose()
