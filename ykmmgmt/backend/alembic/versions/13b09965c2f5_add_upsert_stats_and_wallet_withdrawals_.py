"""add upsert stats and wallet_withdrawals unique constraint

Revision ID: 13b09965c2f5
Revises: a97bfa4a5039
Create Date: 2026-07-29 17:05:58.112409

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "13b09965c2f5"
down_revision: str | Sequence[str] | None = "a97bfa4a5039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add upsert stat columns to import_jobs
    op.add_column(
        "import_jobs",
        sa.Column("rows_inserted", sa.Integer(), server_default="0", nullable=False, comment="新增行数"),
    )
    op.add_column(
        "import_jobs",
        sa.Column("rows_updated", sa.Integer(), server_default="0", nullable=False, comment="更新行数"),
    )
    op.add_column(
        "import_jobs",
        sa.Column("rows_skipped", sa.Integer(), server_default="0", nullable=False, comment="跳过行数"),
    )

    # Deduplicate wallet_withdrawals before adding unique constraint
    # Keep only the first row (lowest id) for each (account_id, sn, operated_at) group
    op.execute(
        sa.text("""
        DELETE FROM wallet_withdrawals
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY account_id, sn, operated_at ORDER BY id
                       ) AS rn
                FROM wallet_withdrawals
            ) sub
            WHERE sub.rn > 1
        )
    """)
    )

    op.create_unique_constraint("uq_wallet_withdrawal_key", "wallet_withdrawals", ["account_id", "sn", "operated_at"])
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_wallet_withdrawal_key", "wallet_withdrawals", type_="unique")
    op.drop_column("import_jobs", "rows_skipped")
    op.drop_column("import_jobs", "rows_updated")
    op.drop_column("import_jobs", "rows_inserted")
    # ### end Alembic commands ###
