"""add chat widget tables (qa_pairs, chat_sessions, chat_messages)

Revision ID: a3f9c2d47b18
Revises: 06a8dafc5163
Create Date: 2026-09-18 11:20:04.512037

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a3f9c2d47b18'
down_revision: Union[str, Sequence[str], None] = '06a8dafc5163'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'qa_pairs',
        sa.Column('id', sa.UUID(), nullable=False, comment='主键ID'),
        sa.Column('question', sa.Text(), nullable=False, comment='标准问题'),
        sa.Column(
            'question_variants',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
            comment='相似问法列表（与 embeddings[1:] 对齐）',
        ),
        sa.Column('answer', sa.Text(), nullable=False, comment='答案（Markdown）'),
        sa.Column(
            'embeddings',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='向量数组，与 [question, *question_variants] 位置对齐',
        ),
        sa.Column('category', sa.String(length=100), nullable=True, comment='分类'),
        sa.Column(
            'is_active',
            sa.Boolean(),
            server_default=sa.text('true'),
            nullable=False,
            comment='是否启用',
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

    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.UUID(), nullable=False, comment='主键ID'),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='所属用户ID'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='创建时间',
        ),
        sa.Column(
            'last_active_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='最后活跃时间',
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chat_sessions_user_id'), 'chat_sessions', ['user_id'], unique=False)

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.UUID(), nullable=False, comment='主键ID'),
        sa.Column('session_id', sa.UUID(), nullable=False, comment='所属会话ID'),
        sa.Column('role', sa.String(length=20), nullable=False, comment='角色: user/assistant'),
        sa.Column('content', sa.Text(), nullable=False, comment='消息内容'),
        sa.Column('matched_qa_id', sa.UUID(), nullable=True, comment='命中的问答ID'),
        sa.Column(
            'matched_variant_index',
            sa.Integer(),
            nullable=True,
            comment='命中的问法索引（0=标准问题，k>=1=第k个相似问法）',
        ),
        sa.Column('similarity_score', sa.Float(), nullable=True, comment='相似度分数'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='创建时间',
        ),
        sa.ForeignKeyConstraint(['matched_qa_id'], ['qa_pairs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_chat_messages_session_id'), 'chat_messages', ['session_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_chat_messages_session_id'), table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index(op.f('ix_chat_sessions_user_id'), table_name='chat_sessions')
    op.drop_table('chat_sessions')
    op.drop_table('qa_pairs')
