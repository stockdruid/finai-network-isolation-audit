"""금융권 ISMS-P 법령 매핑 XLSX → PostgreSQL 적재.

원천: docs/references/금융권_적합_ISMS-P_법령_매핑.xlsx

- 시트 `01_선정기준_요약` → isms_p_criteria (48 인증기준)
- 시트 `02_상세점검항목` → isms_p_checklist_items (191 세부 점검항목)

Usage:
    python scripts/import_isms_p.py            # 재적재 (reset)
    python scripts/import_isms_p.py --dry-run  # 파싱만
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Iterable

import openpyxl
from sqlalchemy import delete

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.models import IsmsPChecklistItem, IsmsPCriterion
from db.session import SessionLocal


REPO_ROOT = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO_ROOT / "docs" / "references" / "금융권_적합_ISMS-P_법령_매핑.xlsx"

VALID_VERDICTS = {"미평가", "적합", "부분적합", "부적합", "증적부족", "적용제외"}


def _rows(ws, min_row: int = 2) -> Iterable[tuple[Any, ...]]:
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


def _norm_section(v: Any) -> str | None:
    """분야명 개행 정규화 ('시스템 및 서비스\n운영관리' → '시스템 및 서비스 운영관리')."""
    s = _s(v)
    if s is None:
        return None
    return " ".join(s.split())


def parse_criteria(wb: openpyxl.Workbook) -> list[dict]:
    """시트 `01_선정기준_요약` → 48 인증기준.

    헤더: 대분류 / 분야 ID / 분야명 / 인증기준 ID / 인증기준명 / 공식 인증기준 / 세부 점검항목 수
    """
    ws = wb["01_선정기준_요약"]
    out: list[dict] = []
    seen: set[str] = set()
    for row in _rows(ws, min_row=2):
        criterion_id = _s(row[3])
        if not criterion_id or criterion_id in seen:
            continue
        seen.add(criterion_id)
        out.append(
            {
                "major_category": _s(row[0]) or "",
                "section_id": _s(row[1]) or "",
                "section_name": _norm_section(row[2]) or "",
                "criterion_id": criterion_id,
                "criterion_name": _s(row[4]) or criterion_id,
                "official_standard": _s(row[5]),
                "checklist_count": int(row[6]) if isinstance(row[6], (int, float)) else 0,
            }
        )
    return out


def parse_checklist_items(
    wb: openpyxl.Workbook, valid_criteria: set[str]
) -> list[dict]:
    """시트 `02_상세점검항목` → 191 세부 점검항목."""
    ws = wb["02_상세점검항목"]
    out: list[dict] = []
    for row in _rows(ws, min_row=2):
        criterion_id = _s(row[3])
        check_number = row[6]
        check_item = _s(row[7])
        if not criterion_id or not check_item or check_number is None:
            continue
        if criterion_id not in valid_criteria:
            # 매핑되지 않는 criterion → 스킵 (FK 무결성)
            continue
        try:
            check_no = int(check_number)
        except (TypeError, ValueError):
            continue
        verdict = _s(row[14]) or "미평가"
        if verdict not in VALID_VERDICTS:
            verdict = "미평가"
        out.append(
            {
                "criterion_id": criterion_id,
                "check_number": check_no,
                "check_item": check_item,
                "aux_standards": _s(row[8]),
                "aux_items": _s(row[9]),
                "related_laws": _s(row[11]),
                "law_content": _s(row[12]),
                "sanction_content": _s(row[13]),
                "verdict": verdict,
                "evidence_location": _s(row[15]),
                "responsible": _s(row[16]),
                "remediation_due": _s(row[17]),
                "review_memo": _s(row[18]),
                "dev_tech_category": _s(row[19]),
                "dev_summary": _s(row[20]),
                "recommended_evidence": _s(row[21]),
                "web_security_ref": _s(row[22]),
            }
        )
    return out


async def load(dry_run: bool = False) -> None:
    if not XLSX_PATH.exists():
        raise FileNotFoundError(f"원천 XLSX 없음: {XLSX_PATH}")

    print(f"[import_isms_p] 원천: {XLSX_PATH}")
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True, read_only=True)

    criteria = parse_criteria(wb)
    valid_ids = {c["criterion_id"] for c in criteria}
    items = parse_checklist_items(wb, valid_ids)

    print(f"  파싱: criteria={len(criteria)}, checklist_items={len(items)}")

    if dry_run:
        print("  [dry-run] DB 미적재. 샘플:")
        for c in criteria[:3]:
            print(f"    - criterion {c['criterion_id']} / {c['criterion_name']}")
        for i in items[:2]:
            print(f"    - {i['criterion_id']}#{i['check_number']}: {i['check_item'][:60]}")
        return

    async with SessionLocal() as session:
        # reset (checklist가 FK로 criteria를 참조하므로 checklist 먼저)
        await session.execute(delete(IsmsPChecklistItem))
        await session.execute(delete(IsmsPCriterion))
        session.add_all([IsmsPCriterion(**c) for c in criteria])
        await session.flush()
        session.add_all([IsmsPChecklistItem(**i) for i in items])
        await session.commit()
        print(
            f"  적재 완료: criteria={len(criteria)}, checklist_items={len(items)}"
        )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="파싱만 하고 DB 미적재")
    args = p.parse_args()
    asyncio.run(load(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
