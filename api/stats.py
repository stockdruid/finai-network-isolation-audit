"""통계 집계 API — 대시보드 차트 데이터 소스."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from db.session import get_session

router = APIRouter()


@router.get("/stats/overview")
async def overview(
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await repo.stats_overview(session)


@router.get("/stats/violations")
async def violations(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await repo.stats_by_violation_type(session)


@router.get("/stats/severity")
async def severity(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await repo.stats_by_severity(session)


@router.get("/stats/timeline")
async def timeline(
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await repo.stats_timeline(session, days=days)
