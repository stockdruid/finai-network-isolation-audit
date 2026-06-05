"""SQLAlchemy 모델 — chatbot_logs v1 단일 진실원.

스키마는 vault `chatbot_logs 스키마 v1 (설계 초안)` 참조.
변경은 alembic revision + PR 리뷰 필수.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
