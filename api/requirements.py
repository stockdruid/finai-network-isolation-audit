"""원천기준 요구사항 → 공통통제 매핑 조회 API — GET /requirements."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from db.session import get_session

router = APIRouter()


@router.get("/requirements")
async def list_requirements(
    source_standard: str | None = Query(default=None),
    control_id: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await repo.list_requirements(
        session,
        source_standard=source_standard,
        control_id=control_id,
        priority=priority,
        limit=limit,
    )
    return [row.to_dict() for row in rows]


@router.get("/requirements/matrix")
async def compliance_matrix(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """공통통제 × 원천기준 매핑 매트릭스."""
    return await repo.compliance_matrix(session)
