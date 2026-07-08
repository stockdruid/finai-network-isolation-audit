"""챗봇 로그 Pydantic 스키마 - 진단 엔진(개발자 B) 노출 포맷.

finai 통합 시 우리 DB의 실제 타입(BigInt/UUID/JSONB list)을 A의 원본 스펙(모두 str)
으로 자동 변환하는 pre-validator를 붙였다.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ChatbotLogOut(BaseModel):
    """진단 엔진(개발자 B)에게 노출되는 로그 1건."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str | None
    request_id: str
    created_at: datetime
    event_type: str
    client_ip: str | None
    user_id: str | None
    tool_name: str | None
    mode: str
    target_url: str | None
    target_provider: str | None
    user_prompt: str
    rag_context: str | None
    llm_response: str | None
    latency_ms: int | None
    status: str
    error_detail: str | None
    guardrail_triggered: str | None
    intentional_vuln_tag: str | None
    pii_detected: bool
    pii_fields: list | None
    security_signals: dict | None
    # INTENTIONAL VULN: raw_request에 평문 자격증명이 그대로 노출됨 (진단 엔진이 탐지)
    raw_request: dict | None
    raw_response: dict | None

    # v6 coercion: 우리 DB의 실제 타입 (BigInt id, UUID, JSONB list) → A 원본 스펙 (str)
    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, v: Any) -> str:
        return str(v) if v is not None else v

    @field_validator("conversation_id", "request_id", mode="before")
    @classmethod
    def _coerce_uuid(cls, v: Any) -> str | None:
        if v is None:
            return None
        if isinstance(v, UUID):
            return str(v)
        return str(v)

    @field_validator("guardrail_triggered", mode="before")
    @classmethod
    def _coerce_guardrail(cls, v: Any) -> str | None:
        # 우리 컬럼은 JSONB list. 첫 요소를 string으로 반환 (없으면 None).
        if v is None or v == [] or v == "":
            return None
        if isinstance(v, list):
            return ", ".join(str(x) for x in v) if v else None
        return str(v)


class LogListResponse(BaseModel):
    items: list[ChatbotLogOut]
    count: int
