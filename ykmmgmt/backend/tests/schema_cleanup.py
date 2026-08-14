"""Test helper: fully purge a dynamically created table after schema tests.

Tests run against the shared dev database and generate real Alembic
migrations. After each test we drop the table directly, delete the
migration files that reference it, and reset alembic_version to the
remaining head so repeated test runs stay reproducible and the repo
does not accumulate test migrations.
"""

from sqlalchemy import text

from app.core.database import engine
from app.services import schema_manager as sm

_VERSIONS_DIR = sm.BACKEND_DIR / "alembic" / "versions"


async def purge_dynamic_tables(*table_names: str) -> None:
    """Drop tables, remove their migrations, and repair the version chain.

    Must receive every table whose migrations may interleave (e.g. FK
    parent/child pairs) so files are removed before the head is recomputed —
    deleting mid-chain files one table at a time breaks the revision map.
    """
    # Remove from runtime registries if a test left them behind
    for name in table_names:
        sm.unregister_dynamic_table(name)

    async with engine.begin() as conn:
        for name in table_names:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))

    for name in table_names:
        for directory in (_VERSIONS_DIR, sm.RUNTIME_MIGRATIONS_DIR):
            for path in directory.glob(f"*{name}*.py"):
                path.unlink(missing_ok=True)

    head = sm.current_migration_head()
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE alembic_version SET version_num = :h"), {"h": head})

    await engine.dispose()


async def purge_dynamic_table(table_name: str) -> None:
    """Single-table convenience wrapper."""
    await purge_dynamic_tables(table_name)


def migration_exists(fragment: str) -> bool:
    """Whether a migration file whose name contains the fragment exists."""
    return any(_VERSIONS_DIR.glob(f"*{fragment}*.py")) or any(sm.RUNTIME_MIGRATIONS_DIR.glob(f"*{fragment}*.py"))
