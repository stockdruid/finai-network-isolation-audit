"""SQLAlchemy 모델 — chatbot_logs + 진단 + 컴플라이언스 매핑.

스키마 이력:
- v1 (20a896e0c6cf): chatbot_logs
- v2 (ccb403c9f67e): diagnosis_results, policy_mappings, compliance_scores
- v3 (b1f4a2d5c7e9): chatbot_logs 확장(실 로그 필드), common_controls, detectors, requirements

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
    """챗봇 이벤트 로그 — chat/signup/login 통합 로그.

    실 로그 스키마(chatbot_sample_logs.jsonl)와 필드 일치.
    """
    __tablename__ = "chatbot_logs"
    __table_args__ = (
        CheckConstraint("mode IN ('internal', 'external')", name="ck_chatbot_logs_mode"),
        CheckConstraint(
            "event_type IN ('chat', 'signup', 'login')",
            name="ck_chatbot_logs_event_type",
        ),
        CheckConstraint(
            "status IN ('success', 'blocked', 'error')",
            name="ck_chatbot_logs_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="now()"
    )
    request_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    conversation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )

    # 이벤트 분류
    event_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="'chat'"
    )
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="'success'"
    )

    # 챗봇 입출력
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    bot_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    rag_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # LLM 호출 정보
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 컴플라이언스·보안 신호
    intentional_vuln_tag: Mapped[str | None] = mapped_column(Text, nullable=True)
    guardrail_triggered: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="'[]'::jsonb"
    )
    pii_detected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    pii_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    security_signals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # 원본 페이로드 (감사증적)
    raw_request: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    diagnoses: Mapped[list["DiagnosisResult"]] = relationship(back_populates="source_log")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "request_id": str(self.request_id),
            "conversation_id": str(self.conversation_id) if self.conversation_id else None,
            "event_type": self.event_type,
            "mode": self.mode,
            "status": self.status,
            "user_input": self.user_input,
            "bot_response": self.bot_response,
            "rag_context": self.rag_context,
            "model_name": self.model_name,
            "target_url": self.target_url,
            "target_provider": self.target_provider,
            "response_time_ms": self.response_time_ms,
            "error_detail": self.error_detail,
            "error_code": self.error_code,
            "intentional_vuln_tag": self.intentional_vuln_tag,
            "guardrail_triggered": self.guardrail_triggered,
            "pii_detected": self.pii_detected,
            "pii_fields": self.pii_fields,
            "security_signals": self.security_signals,
            "flagged": self.flagged,
            "raw_request": self.raw_request,
            "raw_response": self.raw_response,
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


# ---------------------------------------------------------------------------
# v3 — 컴플라이언스 공통통제·Detector·요구사항 매핑
# 원천: 금융_AI_통합_인증_매핑표_프로젝트적용_정제본.xlsx
# ---------------------------------------------------------------------------


class CommonControl(Base):
    """공통통제 마스터 — GOV/DATA/MODEL/OPS/INFRA 도메인.

    원천: 시트 `01_공통통제_마스터`.
    """

    __tablename__ = "common_controls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    control_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)  # GOV-01
    domain: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(Text, nullable=True)  # Critical/High/Medium/Low
    responsible: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_cycle: Mapped[str | None] = mapped_column(Text, nullable=True)
    mapping_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    requirements: Mapped[list["Requirement"]] = relationship(back_populates="control")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "control_id": self.control_id,
            "domain": self.domain,
            "name": self.name,
            "purpose": self.purpose,
            "main_risk": self.main_risk,
            "severity": self.severity,
            "responsible": self.responsible,
            "review_cycle": self.review_cycle,
            "mapping_count": self.mapping_count,
        }


class Detector(Base):
    """MVP12 자동화 Detector 명세.

    원천: 시트 `18_MVP12_자동화명세`.
    """

    __tablename__ = "detectors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    detector_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)  # DET-CHAT-PI-001
    finding_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    area: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # 챗봇/시스템/데이터
    scenario: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str | None] = mapped_column(Text, nullable=True)
    automation: Mapped[str] = mapped_column(Text, nullable=False)  # AUTO/SEMI_AUTO/MANUAL
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    pass_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    fail_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    guardrail: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_standards: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="'[]'::jsonb"
    )
    dev_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str | None] = mapped_column(Text, nullable=True)  # P1/P2/P3
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="'proposed'"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "detector_id": self.detector_id,
            "finding_id": self.finding_id,
            "area": self.area,
            "scenario": self.scenario,
            "target": self.target,
            "automation": self.automation,
            "evidence": self.evidence,
            "pass_criteria": self.pass_criteria,
            "fail_criteria": self.fail_criteria,
            "guardrail": self.guardrail,
            "reference_standards": self.reference_standards,
            "dev_owner": self.dev_owner,
            "policy_owner": self.policy_owner,
            "priority": self.priority,
            "status": self.status,
        }


class Requirement(Base):
    """원천 기준의 개별 요구사항 → 공통통제 매핑 (traceability).

    원천: 시트 `22_프로젝트적용_통합` (269 rows).
    """

    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_standard: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    requirement_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # GAI-1.1
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    control_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("common_controls.control_id", ondelete="SET NULL"), nullable=True
    )
    relationship_type: Mapped[str | None] = mapped_column(Text, nullable=True)  # 직접/부분/간접
    check_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    detector_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="'미평가'"
    )

    control: Mapped["CommonControl | None"] = relationship(back_populates="requirements")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_standard": self.source_standard,
            "requirement_id": self.requirement_id,
            "domain": self.domain,
            "name": self.name,
            "detail": self.detail,
            "control_id": self.control_id,
            "relationship_type": self.relationship_type,
            "check_question": self.check_question,
            "required_evidence": self.required_evidence,
            "detector_id": self.detector_id,
            "priority": self.priority,
            "verdict": self.verdict,
        }
