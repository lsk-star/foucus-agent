"""create coversion

Revision ID: 6420a05f56eb
Revises: de82e2b7fe78
Create Date: 2026-08-28 10:41:49.285821

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = '6420a05f56eb'
down_revision: str | Sequence[str] | None = 'de82e2b7fe78'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('conversation',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('conversation_no', sa.String(length=36), nullable=False),
    sa.Column('user_id', mysql.BIGINT(unsigned=True), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('status', sa.Enum('ACTIVE', 'ARCHIVED', 'DELETED', name='conversationstatus'), nullable=False),
    sa.Column('last_message_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('conversation_no'),
    comment='会话'
    )
    op.create_index(op.f('ix_conversation_user_id'), 'conversation', ['user_id'], unique=False)
    op.create_table('conversation_message',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('conversation_id', sa.BigInteger(), nullable=False),
    sa.Column('message_no', sa.Integer(), nullable=False),
    sa.Column('role', sa.Enum('USER', 'ASSISTANT', name='messagerole'), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('duration_s', sa.Integer(), nullable=True, comment='本次消息生成耗时，单位秒'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversation.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('conversation_id', 'message_no', name='uk_conversation_message_no')
    )
    op.create_index(op.f('ix_conversation_message_conversation_id'), 'conversation_message', ['conversation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_conversation_message_conversation_id'), table_name='conversation_message')
    op.drop_table('conversation_message')
    op.drop_index(op.f('ix_conversation_user_id'), table_name='conversation')
    op.drop_table('conversation')