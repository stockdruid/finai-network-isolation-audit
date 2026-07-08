"""v6 users 테이블 (챗봇 auth 통합) + ChatbotLog synonym

개발자 A 챗봇 코드 통합. auth/users 라우터가 참조하는 users 테이블 추가.
synonym(user_prompt/llm_response/latency_ms)은 ORM만 → DB 변경 없음.

INTENTIONAL VULN: password / ssn 평문 저장 - 진단 엔진이 탐지 대상으로 사용.

Revision ID: e5b3c7f9a2d4
Revises: d2a1b8f4e6c3
Create Date: 2026-07-08 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5b3c7f9a2d4'
down_revision: Union[str, None] = 'd2a1b8f4e6c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('password', sa.String(length=128), nullable=False),
        sa.Column('ssn', sa.String(length=14), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=128), nullable=True),
        sa.Column('session_token', sa.String(length=64), nullable=True),
        sa.Column(
            'created_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
