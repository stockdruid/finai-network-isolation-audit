"""GET /logs — 진단 엔진 폴링용 API (개발자 B 호출).

쿼리:
    mode:  internal | external (필터)
    since: 마지막으로 읽은 chatbot_logs.id (커서)
    limit: 최대 반환 row 수 (default 100)

응답: chatbot_logs row 배열 (id ASC).

추가 엔드포인트:
    GET  /logs/{log_id}   — 개별 로그 상세 (개발자 C, 대시보드용)
    POST /logs/audit      — 배치 감사 + 위반 플래깅 (팀원 heyou32 추가)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from db.models import ChatbotLog
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


@router.post("/logs/audit")
async def audit_chatbot_logs(
    mode: str | None = Query(default=None, pattern="^(internal|external)$"),
    since: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
):
    """배치 감사 — 외부망 호출 로그를 스캔해 위반 플래깅.

    RULE_01 / RULE_03 (망분리 통제) 위반 판정 로직.
    """
    stmt = (
        select(ChatbotLog)
        .where(ChatbotLog.id > since)
        .order_by(ChatbotLog.id.asc())
        .limit(limit)
    )
    if mode is not None:
        stmt = stmt.where(ChatbotLog.mode == mode)

    result = await session.execute(stmt)
    logs = result.scalars().all()

    violation_reports = []
    for log in logs:
        if log.mode == "external" or (
            log.target_url and "api.openai.com" in log.target_url
        ):
            log.flagged = True
            violation_reports.append(
                {
                    "log_id": log.id,
                    "request_id": str(log.request_id),
                    "rule_id": "RULE_01 / RULE_03 위반",
                    "detail": f"망분리 통제 위반 적발: 외부망 모드 가동 혹은 외부 URL({log.target_url}) 직접 호출 탐지.",
                }
            )

    if violation_reports:
        await session.commit()

    return {
        "status": "success",
        "message": "보안 진단 및 DB 플래깅 완료",
        "summary": {
            "total_checked": len(logs),
            "total_violations_flagged": len(violation_reports),
        },
        "violations": violation_reports,
    }
