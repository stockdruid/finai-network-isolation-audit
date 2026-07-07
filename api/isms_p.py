"""금융권 ISMS-P 인증기준 API — GET /isms-p/*."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from db.session import get_session

router = APIRouter(prefix="/isms-p")


@router.get("/criteria")
async def list_criteria(
    major_category: str | None = Query(default=None),
    section_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """금융권 선정 48 인증기준 목록."""
    rows = await repo.list_isms_p_criteria(
        session, major_category=major_category, section_id=section_id
    )
    return [r.to_dict() for r in rows]


@router.get("/criteria/{criterion_id}")
async def get_criterion(
    criterion_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await repo.get_isms_p_criterion(session, criterion_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Criterion not found")
    return row.to_dict()


@router.get("/checklist")
async def list_checklist(
    criterion_id: str | None = Query(default=None),
    verdict: str | None = Query(default=None),
    dev_tech_category: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """세부 점검항목 목록 (191개, 필터 지원)."""
    rows = await repo.list_isms_p_checklist(
        session,
        criterion_id=criterion_id,
        verdict=verdict,
        dev_tech_category=dev_tech_category,
        limit=limit,
    )
    return [r.to_dict() for r in rows]


@router.get("/summary/verdict")
async def summary_by_verdict(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """판정별 집계 (미평가/적합/부적합 등)."""
    return await repo.isms_p_verdict_summary(session)


@router.get("/summary/category")
async def summary_by_category(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """대분류별 인증기준·점검항목 수."""
    return await repo.isms_p_category_summary(session)
