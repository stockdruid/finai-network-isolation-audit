"""v4 pii_types + pii_risk_levels + isms_p_criteria + isms_p_checklist_items

Revision ID: c9e7d3a5f011
Revises: b1f4a2d5c7e9
Create Date: 2026-07-07 18:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c9e7d3a5f011'
down_revision: Union[str, None] = 'b1f4a2d5c7e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. pii_types — 개인정보 유형별 위험도 점수
    # -----------------------------------------------------------------------
    op.create_table(
        'pii_types',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('imprisonment_score', sa.Numeric(4, 1), server_default=sa.text('0.0'), nullable=False),
        sa.Column('fine_score', sa.Numeric(4, 1), server_default=sa.text('0.0'), nullable=False),
        sa.Column('weight_label', sa.Text(), nullable=True),
        sa.Column('weight_value', sa.Numeric(3, 2), server_default=sa.text('1.0'), nullable=False),
        sa.Column('converted_score', sa.Numeric(4, 1), server_default=sa.text('0.0'), nullable=False),
        sa.Column('risk_score', sa.Numeric(4, 1), server_default=sa.text('0.0'), nullable=False),
        sa.Column('legal_basis', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_pii_types_risk_score', 'pii_types', ['risk_score'], unique=False)

    # -----------------------------------------------------------------------
    # 2. pii_risk_levels — 위험 등급 기준 (Critical/High/Medium/Low)
    # -----------------------------------------------------------------------
    op.create_table(
        'pii_risk_levels',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('level_ko', sa.Text(), nullable=False),
        sa.Column('level_en', sa.Text(), nullable=False),
        sa.Column('score_range', sa.Text(), nullable=False),
        sa.Column('min_score', sa.Numeric(5, 1), nullable=False),
        sa.Column('max_score', sa.Numeric(5, 1), nullable=True),
        sa.Column('action_level', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('level_ko'),
        sa.UniqueConstraint('level_en'),
    )

    # -----------------------------------------------------------------------
    # 3. isms_p_criteria — 금융권 ISMS-P 선정 48 인증기준
    # -----------------------------------------------------------------------
    op.create_table(
        'isms_p_criteria',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('major_category', sa.Text(), nullable=False),
        sa.Column('section_id', sa.Text(), nullable=False),
        sa.Column('section_name', sa.Text(), nullable=False),
        sa.Column('criterion_id', sa.Text(), nullable=False),
        sa.Column('criterion_name', sa.Text(), nullable=False),
        sa.Column('official_standard', sa.Text(), nullable=True),
        sa.Column('checklist_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('criterion_id'),
    )
    op.create_index('ix_isms_p_criteria_major_category', 'isms_p_criteria', ['major_category'], unique=False)
    op.create_index('ix_isms_p_criteria_section_id', 'isms_p_criteria', ['section_id'], unique=False)

    # -----------------------------------------------------------------------
    # 4. isms_p_checklist_items — 191 세부 점검항목
    # -----------------------------------------------------------------------
    op.create_table(
        'isms_p_checklist_items',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('criterion_id', sa.Text(), nullable=False),
        sa.Column('check_number', sa.Integer(), nullable=False),
        sa.Column('check_item', sa.Text(), nullable=False),
        sa.Column('aux_standards', sa.Text(), nullable=True),
        sa.Column('aux_items', sa.Text(), nullable=True),
        sa.Column('related_laws', sa.Text(), nullable=True),
        sa.Column('law_content', sa.Text(), nullable=True),
        sa.Column('sanction_content', sa.Text(), nullable=True),
        sa.Column('verdict', sa.Text(), server_default=sa.text("'미평가'"), nullable=False),
        sa.Column('evidence_location', sa.Text(), nullable=True),
        sa.Column('responsible', sa.Text(), nullable=True),
        sa.Column('remediation_due', sa.Text(), nullable=True),
        sa.Column('review_memo', sa.Text(), nullable=True),
        sa.Column('dev_tech_category', sa.Text(), nullable=True),
        sa.Column('dev_summary', sa.Text(), nullable=True),
        sa.Column('recommended_evidence', sa.Text(), nullable=True),
        sa.Column('web_security_ref', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ['criterion_id'], ['isms_p_criteria.criterion_id'], ondelete='CASCADE'
        ),
        sa.CheckConstraint(
            "verdict IN ('미평가','적합','부분적합','부적합','증적부족','적용제외')",
            name='ck_isms_p_verdict',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_isms_p_checklist_items_criterion_id',
        'isms_p_checklist_items',
        ['criterion_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_isms_p_checklist_items_criterion_id', table_name='isms_p_checklist_items')
    op.drop_table('isms_p_checklist_items')
    op.drop_index('ix_isms_p_criteria_section_id', table_name='isms_p_criteria')
    op.drop_index('ix_isms_p_criteria_major_category', table_name='isms_p_criteria')
    op.drop_table('isms_p_criteria')
    op.drop_table('pii_risk_levels')
    op.drop_index('ix_pii_types_risk_score', table_name='pii_types')
    op.drop_table('pii_types')
