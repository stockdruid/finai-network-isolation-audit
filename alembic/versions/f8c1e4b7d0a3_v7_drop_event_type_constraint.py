"""v7 chatbot_logs event_type CHECK constraint 완화

A 챗봇 통합으로 event_type 값이 확장됨:
- 기존: chat / signup / login
- 추가: admin_access, user_lookup, guardrail, ollama_chat, external_llm, auth, llm_error, ...

CHECK constraint 삭제 (제약 없이 자유 값 허용).

Revision ID: f8c1e4b7d0a3
Revises: e5b3c7f9a2d4
Create Date: 2026-07-08 15:15:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'f8c1e4b7d0a3'
down_revision: Union[str, None] = 'e5b3c7f9a2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('ck_chatbot_logs_event_type', 'chatbot_logs', type_='check')


def downgrade() -> None:
    op.create_check_constraint(
        'ck_chatbot_logs_event_type',
        'chatbot_logs',
        "event_type IN ('chat', 'signup', 'login')",
    )
