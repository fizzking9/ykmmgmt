"""add_unique_constraint_visualization_name

Revision ID: 5c8f2a91d4e7
Revises: 4f11ac803470
Create Date: 2026-08-10 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5c8f2a91d4e7'
down_revision: Union[str, Sequence[str], None] = '4f11ac803470'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint('uq_visualizations_name', 'visualizations', ['name'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_visualizations_name', 'visualizations', type_='unique')
