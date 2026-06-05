"""v1_chatbot_logs

Revision ID: 20a896e0c6cf
Revises: 
Create Date: 2026-06-05 14:09:04.636638
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '20a896e0c6cf'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chatbot_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('request_id', sa.UUID(), nullable=False),
        sa.Column('mode', sa.Text(), nullable=False),
        sa.Column('user_input', sa.Text(), nullable=False),
        sa.Column('bot_response', sa.Text(), nullable=True),
        sa.Column('model_name', sa.Text(), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('target_url', sa.Text(), nullable=True),
        sa.Column('intentional_vuln_tag', sa.Text(), nullable=True),
        sa.Column('guardrail_triggered', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('flagged', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('error_code', sa.Text(), nullable=True),
        sa.CheckConstraint("mode IN ('internal', 'external')", name='ck_chatbot_logs_mode'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chatbot_logs_request_id', 'chatbot_logs', ['request_id'], unique=False)
    op.create_index('ix_chatbot_logs_mode_id', 'chatbot_logs', ['mode', 'id'], unique=False)
    op.create_index('ix_chatbot_logs_created_at', 'chatbot_logs', [sa.text('created_at DESC')], unique=False)
    op.create_index(
        'ix_chatbot_logs_vuln_tag',
        'chatbot_logs',
        ['intentional_vuln_tag'],
        unique=False,
        postgresql_where=sa.text('intentional_vuln_tag IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_chatbot_logs_vuln_tag', table_name='chatbot_logs')
    op.drop_index('ix_chatbot_logs_created_at', table_name='chatbot_logs')
    op.drop_index('ix_chatbot_logs_mode_id', table_name='chatbot_logs')
    op.drop_index('ix_chatbot_logs_request_id', table_name='chatbot_logs')
    op.drop_table('chatbot_logs')
