"""Repository — Fail-Loud 정책.

DB write 실패 시 즉시 503 (HTTPException) 으로 노출. 진단 누락 방지.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    ChatbotLog,
    CommonControl,
    ComplianceScore,
    Detector,
    DiagnosisResult,
    IsmsPChecklistItem,
    IsmsPCriterion,
    PiiRiskLevel,
    PiiType,
    PolicyMapping,
    Requirement,
)


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


# ---------------------------------------------------------------------------
# CommonControl
# ---------------------------------------------------------------------------

async def list_controls(
    session: AsyncSession,
    *,
    domain: str | None = None,
    severity: str | None = None,
) -> list[CommonControl]:
    stmt = select(CommonControl).order_by(CommonControl.control_id)
    if domain is not None:
        stmt = stmt.where(CommonControl.domain == domain)
    if severity is not None:
        stmt = stmt.where(CommonControl.severity == severity)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_control(session: AsyncSession, control_id: str) -> CommonControl | None:
    stmt = select(CommonControl).where(CommonControl.control_id == control_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

async def list_detectors(
    session: AsyncSession,
    *,
    area: str | None = None,
    priority: str | None = None,
    automation: str | None = None,
) -> list[Detector]:
    stmt = select(Detector).order_by(Detector.priority, Detector.detector_id)
    if area is not None:
        stmt = stmt.where(Detector.area == area)
    if priority is not None:
        stmt = stmt.where(Detector.priority == priority)
    if automation is not None:
        stmt = stmt.where(Detector.automation == automation)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_detector(session: AsyncSession, detector_id: str) -> Detector | None:
    stmt = select(Detector).where(Detector.detector_id == detector_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Requirement
# ---------------------------------------------------------------------------

async def list_requirements(
    session: AsyncSession,
    *,
    source_standard: str | None = None,
    control_id: str | None = None,
    priority: str | None = None,
    limit: int = 500,
) -> list[Requirement]:
    stmt = select(Requirement).order_by(Requirement.source_standard, Requirement.requirement_id)
    if source_standard is not None:
        stmt = stmt.where(Requirement.source_standard == source_standard)
    if control_id is not None:
        stmt = stmt.where(Requirement.control_id == control_id)
    if priority is not None:
        stmt = stmt.where(Requirement.priority == priority)
    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def compliance_matrix(session: AsyncSession) -> list[dict]:
    """공통통제 × 원천기준 크로스탭 — 매핑 매트릭스."""
    stmt = (
        select(
            Requirement.source_standard,
            Requirement.control_id,
            func.count(Requirement.id).label("count"),
        )
        .group_by(Requirement.source_standard, Requirement.control_id)
        .order_by(Requirement.source_standard, Requirement.control_id)
    )
    result = await session.execute(stmt)
    return [
        {"source_standard": r[0], "control_id": r[1], "count": r[2]}
        for r in result.all()
    ]


# ---------------------------------------------------------------------------
# v4 — PII 위험도
# ---------------------------------------------------------------------------

async def list_pii_types(
    session: AsyncSession,
    *,
    min_score: float | None = None,
) -> list[PiiType]:
    stmt = select(PiiType).order_by(PiiType.risk_score.desc(), PiiType.name)
    if min_score is not None:
        stmt = stmt.where(PiiType.risk_score >= min_score)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_pii_risk_levels(session: AsyncSession) -> list[PiiRiskLevel]:
    stmt = select(PiiRiskLevel).order_by(PiiRiskLevel.min_score.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def aggregate_pii_risk_from_logs(
    session: AsyncSession, *, limit: int = 1000
) -> dict:
    """챗봇 로그 전체를 훑어 pii_fields 합산 → 위험도 판정.

    대시보드 hero 밴드 및 발표 실시간 KPI 소스.
    - `pii_detected=True` 로그만 대상
    - `pii_fields` 원본 라벨을 `core.pii_resolver`로 정규화
    - 정본별 등장 횟수 × risk_score 합산
    """
    from core.pii_resolver import resolve

    stmt = (
        select(ChatbotLog)
        .where(ChatbotLog.pii_detected.is_(True))
        .order_by(ChatbotLog.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    logs = list(result.scalars().all())

    from collections import Counter

    raw_counter: Counter[str] = Counter()
    canonical_counter: Counter[str] = Counter()
    unmatched_counter: Counter[str] = Counter()
    for lg in logs:
        fields = lg.pii_fields or []
        if not isinstance(fields, list):
            continue
        for f in fields:
            raw = str(f)
            raw_counter[raw] += 1
            c = resolve(raw)
            if c is None:
                unmatched_counter[raw] += 1
            else:
                canonical_counter[c] += 1

    types_stmt = select(PiiType)
    types_result = await session.execute(types_stmt)
    by_name = {t.name: t for t in types_result.scalars().all()}

    total_score = 0.0
    by_type: list[dict] = []
    for name, count in canonical_counter.most_common():
        pii = by_name.get(name)
        if pii is None:
            continue
        contribution = float(pii.risk_score) * count
        total_score += contribution
        by_type.append(
            {
                "name": name,
                "count": count,
                "risk_score": float(pii.risk_score),
                "contribution": round(contribution, 2),
            }
        )

    lvl_stmt = select(PiiRiskLevel).order_by(PiiRiskLevel.min_score.desc())
    lvl_result = await session.execute(lvl_stmt)
    picked = None
    for lv in lvl_result.scalars().all():
        if total_score >= float(lv.min_score):
            picked = lv
            break

    return {
        "pii_log_count": len(logs),
        "total_score": round(total_score, 2),
        "level": picked.to_dict() if picked else None,
        "by_type": by_type,
        "unmatched": [
            {"raw": raw, "count": cnt}
            for raw, cnt in unmatched_counter.most_common()
        ],
        "raw_field_counts": [
            {"raw": raw, "count": cnt} for raw, cnt in raw_counter.most_common()
        ],
    }


async def score_pii_fields(
    session: AsyncSession, field_names: list[str]
) -> dict:
    """입력된 PII 필드 목록의 합산 위험도 + 등급 판정.

    챗봇 로그 `pii_fields`(원본 라벨: `ssn`, `email`, `customer_name`, `phone` 등)를
    `core.pii_resolver`로 정본 명칭에 매핑한 뒤 `pii_types.risk_score`를 조회한다.

    응답:
        matched:   정규화 매칭된 PiiType 목록
        unmatched: 별칭 사전에서도 못 찾은 원본 라벨
        resolved_map: 원본 → 정본 매핑 (감사증적)
        total_score: 합산 위험도
        level: 판정된 PiiRiskLevel
    """
    from core.pii_resolver import resolve

    if not field_names:
        return {
            "matched": [],
            "unmatched": [],
            "resolved_map": {},
            "total_score": 0.0,
            "level": None,
        }

    resolved_map: dict[str, str | None] = {n: resolve(n) for n in field_names}
    canonical = [c for c in resolved_map.values() if c is not None]
    unmatched = [orig for orig, c in resolved_map.items() if c is None]

    matched: list[PiiType] = []
    total = 0.0
    if canonical:
        stmt = select(PiiType).where(PiiType.name.in_(canonical))
        result = await session.execute(stmt)
        by_name = {m.name: m for m in result.scalars().all()}
        # 매칭 결과 리스트는 canonical 등장 횟수에 따라 총점 계산 (동일 유형 복수 유출은 합산)
        for c in canonical:
            m = by_name.get(c)
            if m is None:
                continue
            matched.append(m)
            total += float(m.risk_score)

    lvl_stmt = select(PiiRiskLevel).order_by(PiiRiskLevel.min_score.desc())
    lvl_result = await session.execute(lvl_stmt)
    picked = None
    for lv in lvl_result.scalars().all():
        if total >= float(lv.min_score):
            picked = lv
            break

    return {
        "matched": [m.to_dict() for m in matched],
        "unmatched": unmatched,
        "resolved_map": resolved_map,
        "total_score": round(total, 2),
        "level": picked.to_dict() if picked else None,
    }


# ---------------------------------------------------------------------------
# v4 — ISMS-P
# ---------------------------------------------------------------------------

async def list_isms_p_criteria(
    session: AsyncSession,
    *,
    major_category: str | None = None,
    section_id: str | None = None,
) -> list[IsmsPCriterion]:
    stmt = select(IsmsPCriterion).order_by(IsmsPCriterion.criterion_id)
    if major_category is not None:
        stmt = stmt.where(IsmsPCriterion.major_category == major_category)
    if section_id is not None:
        stmt = stmt.where(IsmsPCriterion.section_id == section_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_isms_p_criterion(
    session: AsyncSession, criterion_id: str
) -> IsmsPCriterion | None:
    stmt = select(IsmsPCriterion).where(IsmsPCriterion.criterion_id == criterion_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_isms_p_checklist(
    session: AsyncSession,
    *,
    criterion_id: str | None = None,
    verdict: str | None = None,
    dev_tech_category: str | None = None,
    limit: int = 500,
) -> list[IsmsPChecklistItem]:
    stmt = select(IsmsPChecklistItem).order_by(
        IsmsPChecklistItem.criterion_id, IsmsPChecklistItem.check_number
    )
    if criterion_id is not None:
        stmt = stmt.where(IsmsPChecklistItem.criterion_id == criterion_id)
    if verdict is not None:
        stmt = stmt.where(IsmsPChecklistItem.verdict == verdict)
    if dev_tech_category is not None:
        stmt = stmt.where(IsmsPChecklistItem.dev_tech_category == dev_tech_category)
    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def isms_p_verdict_summary(session: AsyncSession) -> list[dict]:
    """판정별 세부 점검항목 집계 (미평가/적합/부적합 등)."""
    stmt = (
        select(
            IsmsPChecklistItem.verdict,
            func.count(IsmsPChecklistItem.id).label("count"),
        )
        .group_by(IsmsPChecklistItem.verdict)
        .order_by(func.count(IsmsPChecklistItem.id).desc())
    )
    result = await session.execute(stmt)
    return [{"verdict": r[0], "count": r[1]} for r in result.all()]


async def isms_p_category_summary(session: AsyncSession) -> list[dict]:
    """대분류별 인증기준 수 + 세부 점검항목 수."""
    crit_stmt = (
        select(
            IsmsPCriterion.major_category,
            func.count(IsmsPCriterion.id).label("criterion_count"),
            func.sum(IsmsPCriterion.checklist_count).label("checklist_count"),
        )
        .group_by(IsmsPCriterion.major_category)
        .order_by(IsmsPCriterion.major_category)
    )
    result = await session.execute(crit_stmt)
    return [
        {
            "major_category": r[0],
            "criterion_count": r[1],
            "checklist_count": int(r[2] or 0),
        }
        for r in result.all()
    ]
