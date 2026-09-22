"""add qa_pairs.embedding_model (encoder that produced each stored vector)

Revision ID: b7c41d9e2f55
Revises: a3f9c2d47b18
Create Date: 2026-09-18 14:10:22.481193

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7c41d9e2f55'
down_revision: Union[str, Sequence[str], None] = 'a3f9c2d47b18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'qa_pairs',
        sa.Column(
            'embedding_model',
            sa.String(length=200),
            nullable=True,
            comment='生成 embeddings 的向量模型（NULL 或不等当前模型 → 待重建）',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('qa_pairs', 'embedding_model')
