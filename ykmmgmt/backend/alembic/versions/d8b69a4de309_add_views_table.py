"""add_views_table

Revision ID: d8b69a4de309
Revises: 70a297ea8ba6
Create Date: 2026-08-05 14:00:05.528231

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd8b69a4de309'
down_revision: str | Sequence[str] | None = '70a297ea8ba6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'views',
        sa.Column('id', sa.UUID(), nullable=False, comment='主键ID'),
        sa.Column('name', sa.String(length=255), nullable=False, comment='视图名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='视图描述'),
        sa.Column(
            'config_json',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment='视图配置（JSON）',
        ),
        sa.Column(
            'generated_sql', sa.Text(), nullable=True, comment='生成的参数化SQL'
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='创建时间',
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='更新时间',
        ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('views')
