"""Repository — Fail-Loud 정책.

DB write 실패 시 즉시 503 (HTTPException) 으로 노출. 진단 누락 방지.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ChatbotLog, ComplianceScore, DiagnosisResult, PolicyMapping


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

async def _insert(session: AsyncSession, obj: Any, label: str) -> Any:
    try:
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{label} insert failed: {type(exc).__name__}",
        ) from exc
    return obj


# ---------------------------------------------------------------------------
# ChatbotLog
# ---------------------------------------------------------------------------

async def insert_log(session: AsyncSession, **fields: Any) -> ChatbotLog:
    return await _insert(session, ChatbotLog(**fields), "chatbot_logs")


async def get_log_by_id(session: AsyncSession, log_id: int) -> ChatbotLog | None:
    return await session.get(ChatbotLog, log_id)


async def list_logs(
    session: AsyncSession,
    *,
    mode: str | None = None,
    since: int = 0,
    limit: int = 100,
) -> list[ChatbotLog]:
    stmt = select(ChatbotLog).where(ChatbotLog.id > since)
    if mode is not None:
        stmt = stmt.where(ChatbotLog.mode == mode)
    stmt = stmt.order_by(ChatbotLog.id.asc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# DiagnosisResult
# ---------------------------------------------------------------------------

async def insert_diagnosis(session: AsyncSession, **fields: Any) -> DiagnosisResult:
    return await _insert(session, DiagnosisResult(**fields), "diagnosis_results")


async def list_diagnoses(
    session: AsyncSession,
    *,
    severity: str | None = None,
    source_log_id: int | None = None,
    since: int = 0,
    limit: int = 100,
) -> list[DiagnosisResult]:
    stmt = select(DiagnosisResult).where(DiagnosisResult.id > since)
    if severity is not None:
        stmt = stmt.where(DiagnosisResult.severity == severity)
    if source_log_id is not None:
        stmt = stmt.where(DiagnosisResult.source_log_id == source_log_id)
    stmt = stmt.order_by(DiagnosisResult.id.asc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# PolicyMapping
# ---------------------------------------------------------------------------

async def list_policies(
    session: AsyncSession,
    *,
    category: str | None = None,
) -> list[PolicyMapping]:
    stmt = select(PolicyMapping).order_by(PolicyMapping.category, PolicyMapping.code)
    if category is not None:
        stmt = stmt.where(PolicyMapping.category == category)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# ComplianceScore
# ---------------------------------------------------------------------------

async def insert_score(session: AsyncSession, **fields: Any) -> ComplianceScore:
    return await _insert(session, ComplianceScore(**fields), "compliance_scores")


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

async def stats_overview(session: AsyncSession) -> dict:
    total = await session.scalar(select(func.count(DiagnosisResult.id)))
    violations = await session.scalar(
        select(func.count(DiagnosisResult.id)).where(DiagnosisResult.correct == False)  # noqa: E712
    )
    correct = await session.scalar(
        select(func.count(DiagnosisResult.id)).where(DiagnosisResult.correct == True)  # noqa: E712
    )
    log_count = await session.scalar(select(func.count(ChatbotLog.id)))
    return {
        "total_diagnoses": total or 0,
        "violations_detected": violations or 0,
        "correct_detections": correct or 0,
        "total_logs": log_count or 0,
        "accuracy": round(correct / total * 100, 1) if total else 0.0,
    }


async def stats_by_violation_type(session: AsyncSession) -> list[dict]:
    stmt = (
        select(DiagnosisResult.violation_type, func.count(DiagnosisResult.id).label("count"))
        .group_by(DiagnosisResult.violation_type)
        .order_by(func.count(DiagnosisResult.id).desc())
    )
    result = await session.execute(stmt)
    return [{"violation_type": r[0], "count": r[1]} for r in result.all()]


async def stats_by_severity(session: AsyncSession) -> list[dict]:
    stmt = (
        select(DiagnosisResult.severity, func.count(DiagnosisResult.id).label("count"))
        .group_by(DiagnosisResult.severity)
        .order_by(func.count(DiagnosisResult.id).desc())
    )
    result = await session.execute(stmt)
    return [{"severity": r[0], "count": r[1]} for r in result.all()]


async def stats_timeline(session: AsyncSession, *, days: int = 30) -> list[dict]:
    from sqlalchemy import text
    stmt = text(
        "SELECT date(created_at) AS date, count(*) AS count "
        "FROM diagnosis_results "
        "WHERE created_at >= now() - make_interval(days => :days) "
        "GROUP BY date(created_at) ORDER BY date"
    )
    result = await session.execute(stmt, {"days": days})
    return [{"date": str(r[0]), "count": r[1]} for r in result.all()]


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

async def generate_report(session: AsyncSession, scan_id: str) -> ComplianceScore:
    overview = await stats_overview(session)
    total = overview["total_diagnoses"]
    correct = overview["correct_detections"]
    violations = overview["violations_detected"]
    accuracy = overview["accuracy"]

    by_severity = await stats_by_severity(session)
    by_violation = await stats_by_violation_type(session)

    passed = correct
    failed = violations
    warns = max(total - passed - failed, 0)
    score = round(passed / total * 100, 2) if total else 0.0

    return await insert_score(
        session,
        scan_id=scan_id,
        total_score=score,
        passed=passed,
        failed=failed,
        warnings=warns,
        details={
            "accuracy": accuracy,
            "total_logs": overview["total_logs"],
            "by_severity": by_severity,
            "by_violation_type": by_violation,
        },
    )


async def get_report(session: AsyncSession, report_id: int) -> ComplianceScore | None:
    return await session.get(ComplianceScore, report_id)
