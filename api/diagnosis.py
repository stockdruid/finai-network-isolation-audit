"""진단 결과 API — 개발자 B가 POST, 대시보드가 GET."""
from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from db.session import get_session

router = APIRouter()


class DiagnosisCreate(BaseModel):
    source_log_id: int
    violation_type: str
    severity: str = Field(pattern="^(critical|high|medium|low|info)$")
    matched_target_url: str | None = None
    regulation_reference: dict = Field(default_factory=dict)
    correct: bool | None = None


@router.post("/diagnosis", status_code=201)
async def create_diagnosis(
    body: DiagnosisCreate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await repo.insert_diagnosis(session, **body.model_dump())
    return row.to_dict()


@router.get("/diagnosis")
async def list_diagnoses(
    severity: str | None = Query(default=None, pattern="^(critical|high|medium|low|info)$"),
    source_log_id: int | None = Query(default=None),
    since: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await repo.list_diagnoses(
        session, severity=severity, source_log_id=source_log_id, since=since, limit=limit,
    )
    return [row.to_dict() for row in rows]
