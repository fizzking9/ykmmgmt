"""Container startup migrations.

Guards against the database referencing a revision that is not present in
this image (e.g. Schema Manager runtime migrations that only ever existed
on the machine that created them), then applies all pending migrations.
"""

import asyncio
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.core.config import settings


async def current_db_revision() -> str | None:
    """The DB's alembic_version, or None on a fresh (unmigrated) database."""
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as conn:
            exists = await conn.execute(
                text("SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version'")
            )
            if exists.first() is None:
                return None
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.first()
            return row[0] if row else None
    finally:
        await engine.dispose()


def main() -> None:
    config = Config("alembic.ini")
    script_dir = ScriptDirectory.from_config(config)
    known_revisions = {rev.revision for rev in script_dir.walk_revisions()}

    current = asyncio.run(current_db_revision())
    if current is not None and current not in known_revisions:
        sys.stderr.write(
            f"ERROR: database schema version '{current}' is not present in this image.\n"
            "The database was migrated on another machine with Schema Manager runtime\n"
            "migrations that were never squashed into a version-controlled baseline.\n"
            "\n"
            "Fix: from a checkout that can still see those runtime migration files\n"
            "(the machine that created the missing tables), run:\n"
            "    python -m scripts.squash_runtime_migrations\n"
            "then rebuild and redeploy the image.\n"
        )
        sys.exit(1)

    print("Applying database migrations...")
    command.upgrade(config, "head")
    print("Migrations up to date.")


if __name__ == "__main__":
    main()
