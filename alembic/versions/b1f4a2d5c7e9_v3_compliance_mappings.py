"""v3 chatbot_logs 확장 + common_controls + detectors + requirements

Revision ID: b1f4a2d5c7e9
Revises: ccb403c9f67e
Create Date: 2026-07-03 10:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b1f4a2d5c7e9'
down_revision: Union[str, None] = 'ccb403c9f67e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. chatbot_logs 확장 — 실 로그(chatbot_sample_logs.jsonl) 필드
    # -----------------------------------------------------------------------
    op.add_column(
        'chatbot_logs',
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f('ix_chatbot_logs_conversation_id'),
        'chatbot_logs',
        ['conversation_id'],
        unique=False,
    )
    op.add_column(
        'chatbot_logs',
        sa.Column('event_type', sa.Text(), server_default=sa.text("'chat'"), nullable=False),
    )
    op.add_column(
        'chatbot_logs',
        sa.Column('status', sa.Text(), server_default=sa.text("'success'"), nullable=False),
    )
    op.add_column('chatbot_logs', sa.Column('rag_context', sa.Text(), nullable=True))
    op.add_column('chatbot_logs', sa.Column('target_provider', sa.Text(), nullable=True))
    op.add_column('chatbot_logs', sa.Column('error_detail', sa.Text(), nullable=True))
    op.add_column(
        'chatbot_logs',
        sa.Column('pii_detected', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.add_column(
        'chatbot_logs',
        sa.Column('pii_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'chatbot_logs',
        sa.Column('security_signals', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'chatbot_logs',
        sa.Column('raw_request', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'chatbot_logs',
        sa.Column('raw_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # model_name → nullable (auth 이벤트는 model 없음)
    op.alter_column('chatbot_logs', 'model_name', existing_type=sa.Text(), nullable=True)

    op.create_check_constraint(
        'ck_chatbot_logs_event_type',
        'chatbot_logs',
        "event_type IN ('chat', 'signup', 'login')",
    )
    op.create_check_constraint(
        'ck_chatbot_logs_status',
        'chatbot_logs',
        "status IN ('success', 'blocked', 'error')",
    )

    # -----------------------------------------------------------------------
    # 2. common_controls — 공통통제 마스터
    # -----------------------------------------------------------------------
    op.create_table(
        'common_controls',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('control_id', sa.Text(), nullable=False),
        sa.Column('domain', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('purpose', sa.Text(), nullable=True),
        sa.Column('main_risk', sa.Text(), nullable=True),
        sa.Column('severity', sa.Text(), nullable=True),
        sa.Column('responsible', sa.Text(), nullable=True),
        sa.Column('review_cycle', sa.Text(), nullable=True),
        sa.Column('mapping_count', sa.Integer(), server_default='0', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('control_id'),
    )
    op.create_index(
        op.f('ix_common_controls_domain'),
        'common_controls',
        ['domain'],
        unique=False,
    )

    # -----------------------------------------------------------------------
    # 3. detectors — MVP12 자동화 명세
    # -----------------------------------------------------------------------
    op.create_table(
        'detectors',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('detector_id', sa.Text(), nullable=False),
        sa.Column('finding_id', sa.Text(), nullable=True),
        sa.Column('area', sa.Text(), nullable=False),
        sa.Column('scenario', sa.Text(), nullable=False),
        sa.Column('target', sa.Text(), nullable=True),
        sa.Column('automation', sa.Text(), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('pass_criteria', sa.Text(), nullable=True),
        sa.Column('fail_criteria', sa.Text(), nullable=True),
        sa.Column('guardrail', sa.Text(), nullable=True),
        sa.Column(
            'reference_standards',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column('dev_owner', sa.Text(), nullable=True),
        sa.Column('policy_owner', sa.Text(), nullable=True),
        sa.Column('priority', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), server_default=sa.text("'proposed'"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('detector_id'),
    )
    op.create_index(op.f('ix_detectors_area'), 'detectors', ['area'], unique=False)

    # -----------------------------------------------------------------------
    # 4. requirements — 원천기준 개별 요구사항 → 공통통제 매핑
    # -----------------------------------------------------------------------
    op.create_table(
        'requirements',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source_standard', sa.Text(), nullable=False),
        sa.Column('requirement_id', sa.Text(), nullable=False),
        sa.Column('domain', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('control_id', sa.Text(), nullable=True),
        sa.Column('relationship_type', sa.Text(), nullable=True),
        sa.Column('check_question', sa.Text(), nullable=True),
        sa.Column('required_evidence', sa.Text(), nullable=True),
        sa.Column('detector_id', sa.Text(), nullable=True),
        sa.Column('priority', sa.Text(), nullable=True),
        sa.Column('verdict', sa.Text(), server_default=sa.text("'미평가'"), nullable=False),
        sa.ForeignKeyConstraint(
            ['control_id'], ['common_controls.control_id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_requirements_source_standard'),
        'requirements',
        ['source_standard'],
        unique=False,
    )
    op.create_index(
        op.f('ix_requirements_requirement_id'),
        'requirements',
        ['requirement_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_requirements_requirement_id'), table_name='requirements')
    op.drop_index(op.f('ix_requirements_source_standard'), table_name='requirements')
    op.drop_table('requirements')

    op.drop_index(op.f('ix_detectors_area'), table_name='detectors')
    op.drop_table('detectors')

    op.drop_index(op.f('ix_common_controls_domain'), table_name='common_controls')
    op.drop_table('common_controls')

    op.drop_constraint('ck_chatbot_logs_status', 'chatbot_logs', type_='check')
    op.drop_constraint('ck_chatbot_logs_event_type', 'chatbot_logs', type_='check')
    op.alter_column('chatbot_logs', 'model_name', existing_type=sa.Text(), nullable=False)
    op.drop_column('chatbot_logs', 'raw_response')
    op.drop_column('chatbot_logs', 'raw_request')
    op.drop_column('chatbot_logs', 'security_signals')
    op.drop_column('chatbot_logs', 'pii_fields')
    op.drop_column('chatbot_logs', 'pii_detected')
    op.drop_column('chatbot_logs', 'error_detail')
    op.drop_column('chatbot_logs', 'target_provider')
    op.drop_column('chatbot_logs', 'rag_context')
    op.drop_column('chatbot_logs', 'status')
    op.drop_column('chatbot_logs', 'event_type')
    op.drop_index(op.f('ix_chatbot_logs_conversation_id'), table_name='chatbot_logs')
    op.drop_column('chatbot_logs', 'conversation_id')
