"""GET /logs — 진단 엔진 폴링용 API (개발자 B 호출).

쿼리:
    mode:  internal | external (필터)
    since: 마지막으로 읽은 chatbot_logs.id (커서)
    limit: 최대 반환 row 수 (default 100)

응답: chatbot_logs row 배열 (id ASC).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ChatbotLog
from db.session import get_session

router = APIRouter()


@router.get("/logs")
async def list_logs(
    mode: str | None = Query(default=None, pattern="^(internal|external)$"),
    since: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    stmt = select(ChatbotLog).where(ChatbotLog.id > since)
    if mode is not None:
        stmt = stmt.where(ChatbotLog.mode == mode)
    stmt = stmt.order_by(ChatbotLog.id.asc()).limit(limit)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [row.to_dict() for row in rows]
