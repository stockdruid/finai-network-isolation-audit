"""금융권 ISMS-P 인증기준 API — GET / PATCH / POST /isms-p/*."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from db.session import get_session

router = APIRouter(prefix="/isms-p")


class VerdictUpdate(BaseModel):
    verdict: str | None = Field(default=None, description="미평가/적합/부분적합/부적합/증적부족/적용제외")
    evidence_location: str | None = None
    responsible: str | None = None
    remediation_due: str | None = None
    review_memo: str | None = None


class BulkVerdictItem(BaseModel):
    item_id: int
    verdict: str | None = None
    evidence_location: str | None = None
    responsible: str | None = None
    remediation_due: str | None = None
    review_memo: str | None = None


class BulkVerdictRequest(BaseModel):
    updates: list[BulkVerdictItem]


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


@router.get("/checklist/{item_id}")
async def get_checklist_item(
    item_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await repo.get_isms_p_checklist_item(session, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    return row.to_dict()


@router.patch("/checklist/{item_id}")
async def update_checklist_item(
    item_id: int,
    payload: VerdictUpdate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """개별 판정·증적·담당자 업데이트 (개발자 B 진단 결과 반영용).

    None 필드는 미변경. verdict는 화이트리스트 검증.
    """
    row = await repo.update_isms_p_verdict(
        session,
        item_id,
        verdict=payload.verdict,
        evidence_location=payload.evidence_location,
        responsible=payload.responsible,
        remediation_due=payload.remediation_due,
        review_memo=payload.review_memo,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    return row.to_dict()


@router.post("/checklist/bulk-verdict")
async def bulk_update_verdict(
    payload: BulkVerdictRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """진단 엔진 배치 판정 반영.

    본문 예시:
        {"updates": [
            {"item_id": 42, "verdict": "적합", "review_memo": "auto: DET-CHAT-PI-001 pass"},
            {"item_id": 43, "verdict": "부적합", "review_memo": "auto: pattern match"}
        ]}
    부분 성공 허용. 잘못된 verdict / 미존재 item_id는 skipped에 담아 응답.
    """
    updates_list = [u.model_dump(exclude_none=False) for u in payload.updates]
    return await repo.bulk_update_isms_p_verdict(session, updates_list)


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
