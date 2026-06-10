"""SQLAlchemy 모델 — chatbot_logs v1 단일 진실원.

스키마는 vault `chatbot_logs 스키마 v1 (설계 초안)` 참조.
변경은 alembic revision + PR 리뷰 필수.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ChatbotLog(Base):
    __tablename__ = "chatbot_logs"
    __table_args__ = (
        CheckConstraint("mode IN ('internal', 'external')", name="ck_chatbot_logs_mode"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    request_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    bot_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    intentional_vuln_tag: Mapped[str | None] = mapped_column(Text, nullable=True)
    guardrail_triggered: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="'[]'::jsonb"
    )
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)

    diagnoses: Mapped[list["DiagnosisResult"]] = relationship(back_populates="source_log")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "request_id": str(self.request_id),
            "mode": self.mode,
            "user_input": self.user_input,
            "bot_response": self.bot_response,
            "model_name": self.model_name,
            "response_time_ms": self.response_time_ms,
            "target_url": self.target_url,
            "intentional_vuln_tag": self.intentional_vuln_tag,
            "guardrail_triggered": self.guardrail_triggered,
            "flagged": self.flagged,
            "error_code": self.error_code,
        }


class DiagnosisResult(Base):
    """진단 엔진 결과 — 개발자 B가 insert."""

    __tablename__ = "diagnosis_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    source_log_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chatbot_logs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    violation_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    matched_target_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    regulation_reference: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="'{}'::jsonb"
    )
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    source_log: Mapped["ChatbotLog"] = relationship(back_populates="diagnoses")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "source_log_id": self.source_log_id,
            "violation_type": self.violation_type,
            "severity": self.severity,
            "matched_target_url": self.matched_target_url,
            "regulation_reference": self.regulation_reference,
            "correct": self.correct,
        }


class PolicyMapping(Base):
    """법령/인증 매핑 — 정책팀 YAML에서 로드."""

    __tablename__ = "policy_mappings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity_weight: Mapped[float] = mapped_column(Numeric(3, 1), nullable=False, server_default="5.0")
    related_rules: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="'[]'::jsonb"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "code": self.code,
            "title": self.title,
            "description": self.description,
            "severity_weight": float(self.severity_weight),
            "related_rules": self.related_rules,
        }


class ComplianceScore(Base):
    """컴플라이언스 점수 집계 — 스캔 단위."""

    __tablename__ = "compliance_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    scan_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    total_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    warnings: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="'{}'::jsonb"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "scan_id": self.scan_id,
            "total_score": float(self.total_score),
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "details": self.details,
        }
