"""GET /logs — 진단 엔진 폴링용 API (개발자 B 호출).

쿼리:
    mode:  internal | external (필터)
    since: 마지막으로 읽은 chatbot_logs.id (커서)
    limit: 최대 반환 row 수 (default 100)

응답: chatbot_logs row 배열 (id ASC).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from db.session import get_session

router = APIRouter()


@router.get("/logs")
async def list_logs(
    mode: str | None = Query(default=None, pattern="^(internal|external)$"),
    since: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await repo.list_logs(session, mode=mode, since=since, limit=limit)
    return [row.to_dict() for row in rows]


@router.get("/logs/{log_id}")
async def get_log(
    log_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    log = await repo.get_log_by_id(session, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Log not found")
    return log.to_dict()
