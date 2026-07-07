"""MVP12 Detector 명세 조회 API — GET /detectors."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from db.session import get_session

router = APIRouter()


@router.get("/detectors")
async def list_detectors(
    area: str | None = Query(default=None),
    priority: str | None = Query(default=None, pattern="^P[1-3]$"),
    automation: str | None = Query(default=None, pattern="^(AUTO|SEMI_AUTO|MANUAL)$"),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await repo.list_detectors(
        session, area=area, priority=priority, automation=automation
    )
    return [row.to_dict() for row in rows]


@router.get("/detectors/{detector_id}")
async def get_detector(
    detector_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await repo.get_detector(session, detector_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Detector not found")
    return row.to_dict()
