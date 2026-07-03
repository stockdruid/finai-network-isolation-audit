"""공통통제 마스터 조회 API — GET /controls."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from db.session import get_session

router = APIRouter()


@router.get("/controls")
async def list_controls(
    domain: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await repo.list_controls(session, domain=domain, severity=severity)
    return [row.to_dict() for row in rows]


@router.get("/controls/{control_id}")
async def get_control(
    control_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await repo.get_control(session, control_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Control not found")
    return row.to_dict()
