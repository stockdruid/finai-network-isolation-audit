"""ChatbotLog repository — Fail-Loud 정책.

DB write 실패 시 즉시 503 (HTTPException) 으로 노출. 진단 누락 방지.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ChatbotLog


async def insert_log(session: AsyncSession, **fields: Any) -> ChatbotLog:
    log = ChatbotLog(**fields)
    try:
        session.add(log)
        await session.commit()
        await session.refresh(log)
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"chatbot_logs insert failed: {type(exc).__name__}",
        ) from exc
    return log
