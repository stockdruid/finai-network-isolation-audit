"""v5 chatbot_logs 추적/방어 필드 (client_ip, user_id, tool_name)

개발자 A 챗봇(finance-compliance-chatbot) JSONL 브릿지용.
진단팀 요청(2026-07-07) 3필드 반영.

Revision ID: d2a1b8f4e6c3
Revises: c9e7d3a5f011
Create Date: 2026-07-07 19:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd2a1b8f4e6c3'
down_revision: Union[str, None] = 'c9e7d3a5f011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('chatbot_logs', sa.Column('client_ip', sa.Text(), nullable=True))
    op.add_column('chatbot_logs', sa.Column('user_id', sa.Text(), nullable=True))
    op.add_column('chatbot_logs', sa.Column('tool_name', sa.Text(), nullable=True))
    op.create_index(
        op.f('ix_chatbot_logs_client_ip'), 'chatbot_logs', ['client_ip'], unique=False
    )
    op.create_index(
        op.f('ix_chatbot_logs_user_id'), 'chatbot_logs', ['user_id'], unique=False
    )
    op.create_index(
        op.f('ix_chatbot_logs_tool_name'), 'chatbot_logs', ['tool_name'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_chatbot_logs_tool_name'), table_name='chatbot_logs')
    op.drop_index(op.f('ix_chatbot_logs_user_id'), table_name='chatbot_logs')
    op.drop_index(op.f('ix_chatbot_logs_client_ip'), table_name='chatbot_logs')
    op.drop_column('chatbot_logs', 'tool_name')
    op.drop_column('chatbot_logs', 'user_id')
    op.drop_column('chatbot_logs', 'client_ip')
