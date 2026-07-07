"""컴플라이언스 매핑 XLSX → PostgreSQL 적재.

원천: docs/references/금융_AI_통합_인증_매핑표_프로젝트적용_정제본.xlsx

- 시트 `01_공통통제_마스터` → common_controls
- 시트 `18_MVP12_자동화명세` → detectors
- 시트 `22_프로젝트적용_통합` → requirements

Usage:
    python scripts/import_compliance_mappings.py            # 전체 재적재
    python scripts/import_compliance_mappings.py --dry-run  # 파싱만
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Iterable

import openpyxl
from sqlalchemy import delete, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.models import CommonControl, Detector, Requirement
from db.session import SessionLocal


REPO_ROOT = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO_ROOT / "docs" / "references" / "금융_AI_통합_인증_매핑표_프로젝트적용_정제본.xlsx"


def _rows(ws, min_row: int = 2) -> Iterable[tuple[Any, ...]]:
    """엑셀 시트의 데이터 행만 반환 (헤더 제외, 완전 빈 행 스킵)."""
    for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if i < min_row:
            continue
        if all(c is None or (isinstance(c, str) and not c.strip()) for c in row):
            continue
        yield row


def _s(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _list_from(v: Any) -> list[str]:
    """콤마/슬래시/줄바꿈 구분 문자열을 리스트로 변환."""
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    txt = str(v)
    for sep in ["\n", ";", "/", "|"]:
        txt = txt.replace(sep, ",")
    return [p.strip() for p in txt.split(",") if p.strip()]


def parse_common_controls(wb: openpyxl.Workbook) -> list[dict]:
    ws = wb["01_공통통제_마스터"]
    out: list[dict] = []
    for row in _rows(ws, min_row=2):
        control_id = _s(row[0])
        if not control_id or not control_id[:3].isalpha():
            continue
        out.append(
            {
                "control_id": control_id,
                "domain": _s(row[1]) or "미분류",
                "name": _s(row[2]) or control_id,
                "purpose": _s(row[3]),
                "main_risk": _s(row[4]),
                "severity": _s(row[5]),
                "responsible": _s(row[6]),
                "review_cycle": _s(row[7]),
                "mapping_count": int(row[8]) if row[8] not in (None, "") else 0,
            }
        )
    return out


def parse_detectors(wb: openpyxl.Workbook) -> list[dict]:
    ws = wb["18_MVP12_자동화명세"]
    out: list[dict] = []
    for row in _rows(ws, min_row=2):
        detector_id = _s(row[2])
        if not detector_id or not detector_id.startswith("DET-"):
            continue
        out.append(
            {
                "detector_id": detector_id,
                "finding_id": _s(row[3]),
                "area": _s(row[1]) or "기타",
                "scenario": _s(row[4]) or detector_id,
                "target": _s(row[5]),
                "automation": _s(row[6]) or "MANUAL",
                "evidence": _s(row[7]),
                "pass_criteria": _s(row[8]),
                "fail_criteria": _s(row[9]),
                "guardrail": _s(row[10]),
                "reference_standards": _list_from(row[11]),
                "dev_owner": _s(row[12]),
                "policy_owner": _s(row[13]),
                "priority": _s(row[14]),
                "status": _s(row[15]) or "proposed",
            }
        )
    return out


def parse_requirements(wb: openpyxl.Workbook) -> list[dict]:
    ws = wb["22_프로젝트적용_통합"]
    out: list[dict] = []
    for row in _rows(ws, min_row=2):
        req_id = _s(row[1])
        if not req_id:
            continue
        out.append(
            {
                "source_standard": _s(row[0]) or "미상",
                "requirement_id": req_id,
                "domain": _s(row[2]),
                "name": _s(row[3]) or req_id,
                "detail": _s(row[4]),
                "control_id": _s(row[5]),
                "relationship_type": _s(row[7]),
                "check_question": _s(row[8]),
                "required_evidence": _s(row[9]),
                "detector_id": _s(row[17]),
                "priority": _s(row[25]),
                "verdict": _s(row[10]) or "미평가",
            }
        )
    return out


async def load(dry_run: bool = False) -> None:
    if not XLSX_PATH.exists():
        raise FileNotFoundError(f"매핑표 XLSX가 없다: {XLSX_PATH}")

    print(f"[읽기] {XLSX_PATH.name}")
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True, read_only=True)

    controls = parse_common_controls(wb)
    detectors = parse_detectors(wb)
    requirements = parse_requirements(wb)
    wb.close()

    print(f"  - 공통통제: {len(controls)}건")
    print(f"  - Detector: {len(detectors)}건")
    print(f"  - 요구사항: {len(requirements)}건")

    if dry_run:
        print("[dry-run] 미저장")
        return

    async with SessionLocal() as session:
        # requirements → detectors → common_controls 순으로 삭제 (FK 안전)
        await session.execute(delete(Requirement))
        await session.execute(delete(Detector))
        await session.execute(delete(CommonControl))
        await session.flush()

        session.add_all([CommonControl(**c) for c in controls])
        session.add_all([Detector(**d) for d in detectors])

        valid_control_ids = {c["control_id"] for c in controls}
        for r in requirements:
            # FK 위반 방지 — control_id 미매칭 시 NULL 처리
            if r["control_id"] and r["control_id"] not in valid_control_ids:
                r["control_id"] = None
        session.add_all([Requirement(**r) for r in requirements])

        await session.commit()

    print("[완료] common_controls / detectors / requirements 재적재 성공")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="파싱만, DB 미변경")
    args = ap.parse_args()
    asyncio.run(load(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
