"""Squash Schema Manager runtime migrations into a version-controlled baseline.

Runtime migrations live in ykmmgmt/runtime_migrations/ (git-ignored, written
by the Schema Manager at runtime). They chain off the last version-controlled
revision in alembic/versions/. A database that has applied them has an
alembic_version pointing at files that exist only on this machine — any
redeploy from a clean image would fail.

This script:
  1. collects the runtime migration chain (from the versioned head onward),
  2. writes a single baseline migration into alembic/versions/ whose
     upgrade()/downgrade() replay every squashed migration in order,
  3. re-stamps the local database from the runtime head to the baseline
     (schema is untouched — only the alembic_version pointer moves),
  4. deletes the squashed runtime files so exactly one head remains.

Re-run after future Schema Manager tables accumulate; commit the generated
baseline file, then rebuild and redeploy the image.
"""

import ast
import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

from alembic.config import Config
from alembic.script import Script, ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

BACKEND_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BACKEND_DIR.parent / "runtime_migrations"
VERSIONS_DIR = BACKEND_DIR / "alembic" / "versions"

_BASELINE_TEMPLATE = '''"""{message}

Revision ID: {revision}
Revises: {down_revision}
Create Date: {create_date}

Squash of {n_runtime} Schema Manager runtime migration(s) — see
scripts/squash_runtime_migrations.py. Regenerated, do not edit by hand.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "{revision}"
down_revision: Union[str, Sequence[str], None] = "{down_revision}"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
{upgrade_body}


def downgrade() -> None:
{downgrade_body}
'''


def _function_body(source: str, name: str) -> str:
    """Source of a module-level function's body, `def` line stripped."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert segment is not None
            return "\n".join(segment.splitlines()[1:]).rstrip()
    raise ValueError(f"function {name!r} not found")


def _is_runtime(script: Script) -> bool:
    return RUNTIME_DIR.resolve() in Path(script.path).resolve().parents


async def _stamp_db(baseline_rev: str, old_revisions: list[str]) -> None:
    """Point alembic_version at the baseline, dropping the squashed rows.

    A plain `alembic stamp` INSERTs a second version row while the runtime
    chain still exists on disk (two heads), so we update the pointer by SQL
    instead — same effect, no ambiguity.
    """
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM alembic_version WHERE version_num NOT IN (:rev)"),
                {"rev": baseline_rev},
            )
            await conn.execute(
                text("UPDATE alembic_version SET version_num = :rev"),
                {"rev": baseline_rev},
            )
    finally:
        await engine.dispose()


def main() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script_dir = ScriptDirectory.from_config(config)

    heads = script_dir.get_heads()
    if len(heads) != 1:
        sys.exit(f"ERROR: expected exactly one migration head, found {len(heads)}: {heads}")

    # Walk the full chain newest → oldest
    chain: list[Script] = list(script_dir.walk_revisions())
    runtime = [s for s in chain if _is_runtime(s)]
    if not runtime:
        print("Nothing to squash — no runtime migrations found.")
        return

    # chain is newest → oldest; runtime subset keeps that order here
    # (also verifies contiguity while at it)
    runtime = list(reversed(runtime))  # oldest → newest
    for prev, cur in zip(runtime, runtime[1:], strict=False):
        if cur.down_revision != prev.revision:
            sys.exit(f"ERROR: runtime chain is not contiguous: {cur.revision} revises {cur.down_revision}")
    parent = runtime[0].down_revision
    if parent is None or _is_runtime(script_dir.get_revision(parent)):
        sys.exit(f"ERROR: runtime chain does not attach to a version-controlled revision (parent={parent})")

    baseline_rev = uuid.uuid4().hex[:12]

    upgrade_parts: list[str] = []
    downgrade_parts: list[str] = []
    for script in runtime:
        source = Path(script.path).read_text(encoding="utf-8")
        header = f"    # ---- {script.revision}: {Path(script.path).name} ----\n"
        upgrade_parts.append(header + _function_body(source, "upgrade"))
        downgrade_parts.append(header + _function_body(source, "downgrade"))

    # downgrade replays in reverse order
    downgrade_parts.reverse()

    content = _BASELINE_TEMPLATE.format(
        message="runtime baseline (Schema Manager dynamic tables)",
        revision=baseline_rev,
        down_revision=parent,
        create_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        n_runtime=len(runtime),
        upgrade_body="\n\n".join(upgrade_parts),
        downgrade_body="\n\n".join(downgrade_parts),
    )

    baseline_path = VERSIONS_DIR / f"{baseline_rev}_runtime_baseline.py"
    baseline_path.write_text(content, encoding="utf-8")
    print(f"Wrote baseline migration {baseline_rev} -> {baseline_path}")
    print(f"  squashed {len(runtime)} runtime migration(s):")
    for script in runtime:
        print(f"    {script.revision}  {Path(script.path).name}")

    # Re-stamp the local database (pointer only — no schema changes)
    try:
        asyncio.run(_stamp_db(baseline_rev, [s.revision for s in runtime]))
    except Exception as exc:  # DB unreachable, etc.
        print(
            f"WARNING: could not stamp the database automatically ({exc}).\n"
            f"Run manually once the database is reachable:\n"
            f"    docker exec <db-container> psql -U <user> -d <db> "
            f"-c \"UPDATE alembic_version SET version_num = '{baseline_rev}'\"\n"
            f"Then delete the squashed runtime files listed above from {RUNTIME_DIR}."
        )
        return
    print(f"Database stamped to baseline revision {baseline_rev}.")

    # Remove the squashed runtime files so exactly one head remains
    for script in runtime:
        Path(script.path).unlink()
    print(f"Deleted {len(runtime)} runtime migration file(s) from {RUNTIME_DIR}.")
    print("Commit the baseline migration file, then rebuild the Docker image.")


if __name__ == "__main__":
    main()
