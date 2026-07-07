"""리포트 생성/조회 API — 컴플라이언스 스캔 결과 스냅샷."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from db.session import get_session

router = APIRouter()

KST = timezone(timedelta(hours=9))


class ReportCreate(BaseModel):
    scan_id: str | None = None


@router.post("/reports/generate", status_code=201)
async def generate_report(
    body: ReportCreate | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    scan_id = (body.scan_id if body and body.scan_id
               else f"scan-{datetime.now(KST).strftime('%Y%m%d-%H%M%S')}")
    report = await repo.generate_report(session, scan_id)
    return report.to_dict()


@router.get("/reports/{report_id}")
async def get_report(
    report_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    report = await repo.get_report(session, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report.to_dict()
