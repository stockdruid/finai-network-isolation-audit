"""개인정보 위험도 산정체계 API — GET /pii-risk/*."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from db.session import get_session

router = APIRouter(prefix="/pii-risk")


@router.get("/types")
async def list_pii_types(
    min_score: float | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """개인정보 유형별 위험도 점수 목록 (15개 유형)."""
    rows = await repo.list_pii_types(session, min_score=min_score)
    return [r.to_dict() for r in rows]


@router.get("/levels")
async def list_risk_levels(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """위험 등급 기준 (Critical/High/Medium/Low)."""
    rows = await repo.list_pii_risk_levels(session)
    return [r.to_dict() for r in rows]


class ScoreRequest(BaseModel):
    fields: list[str]


@router.post("/score")
async def score_pii(
    payload: ScoreRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """PII 필드 목록 → 합산 위험도 + 등급 판정.

    예시: {"fields": ["주민등록번호", "이메일"]}
    """
    return await repo.score_pii_fields(session, payload.fields)
