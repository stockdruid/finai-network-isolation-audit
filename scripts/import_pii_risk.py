"""개인정보 위험도 산정체계 XLSX → PostgreSQL 적재.

원천: docs/references/개인정보_위험도_산정체계.xlsx

- 시트 `개인정보 유형별 위험도` → pii_types (17개 유형)
- 시트 `위험 등급 기준` → pii_risk_levels (Critical/High/Medium/Low)

Usage:
    python scripts/import_pii_risk.py            # 재적재 (reset)
    python scripts/import_pii_risk.py --dry-run  # 파싱만
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import openpyxl
from sqlalchemy import delete

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.models import PiiRiskLevel, PiiType
from db.session import SessionLocal


REPO_ROOT = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO_ROOT / "docs" / "references" / "개인정보_위험도_산정체계.xlsx"


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


def _f(v: Any) -> float:
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def parse_pii_types(wb: openpyxl.Workbook) -> list[dict]:
    """시트 `개인정보 유형별 위험도` 파싱.

    헤더(R2): 개인정보 유형 / 징역 기준 점수 / 금액 기준 점수 / 가중치 적용 /
              환산 점수 / 위험도 계산 / 최종 위험도 점수 / 법령 근거
    """
    ws = wb["개인정보 유형별 위험도"]
    out: list[dict] = []
    for row in _rows(ws, min_row=3):
        name = _s(row[0])
        if not name or name.startswith("■"):  # 색상 범례 스킵
            continue
        # 가중치 라벨에서 배수 추출 ("x 1.0 (벌금)" → 1.0)
        weight_label = _s(row[3])
        weight_value = 1.0
        if weight_label:
            import re
            m = re.search(r"x\s*([\d.]+)", weight_label)
            if m:
                try:
                    weight_value = float(m.group(1))
                except ValueError:
                    pass
        out.append(
            {
                "name": name,
                "imprisonment_score": _f(row[1]),
                "fine_score": _f(row[2]),
                "weight_label": weight_label,
                "weight_value": weight_value,
                "converted_score": _f(row[4]),
                "risk_score": _f(row[6]),
                "legal_basis": _s(row[7]),
            }
        )
    return out


def parse_risk_levels(wb: openpyxl.Workbook) -> list[dict]:
    """시트 `위험 등급 기준` 파싱 (헤더 R2, 4개 등급 R3~R6).

    R7 이후 '등급별 해당 개인정보 유형' 서브 섹션은 스킵 (컬럼 수도 다름).
    """
    VALID = {"Critical", "High", "Medium", "Low"}
    ws = wb["위험 등급 기준"]
    out: list[dict] = []
    for row in _rows(ws, min_row=3):
        if len(row) < 5:
            continue
        level_ko = _s(row[0])
        level_en = _s(row[1])
        if not level_ko or not level_en or level_en not in VALID:
            continue
        score_range = _s(row[2]) or ""
        min_score, max_score = _parse_range(score_range)
        out.append(
            {
                "level_ko": level_ko,
                "level_en": level_en,
                "score_range": score_range,
                "min_score": min_score,
                "max_score": max_score,
                "action_level": _s(row[3]) or "",
                "description": _s(row[4]),
            }
        )
    return out


def _parse_range(text: str) -> tuple[float, float | None]:
    """'30점 이상' → (30, None), '20 ~ 29점' → (20, 29), '10점 미만' → (0, 9.9)."""
    import re
    text = text.replace(" ", "")
    if "이상" in text:
        m = re.search(r"([\d.]+)", text)
        return (float(m.group(1)) if m else 0.0, None)
    if "미만" in text:
        m = re.search(r"([\d.]+)", text)
        return (0.0, float(m.group(1)) - 0.01 if m else None)
    m = re.search(r"([\d.]+)~([\d.]+)", text)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    return (0.0, None)


async def load(dry_run: bool = False) -> None:
    if not XLSX_PATH.exists():
        raise FileNotFoundError(f"원천 XLSX 없음: {XLSX_PATH}")

    print(f"[import_pii_risk] 원천: {XLSX_PATH}")
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True, read_only=True)

    pii_types = parse_pii_types(wb)
    risk_levels = parse_risk_levels(wb)

    print(f"  파싱: pii_types={len(pii_types)}, pii_risk_levels={len(risk_levels)}")

    if dry_run:
        print("  [dry-run] DB 미적재. 샘플:")
        for r in pii_types[:3]:
            print(f"    - {r}")
        for r in risk_levels:
            print(f"    - {r}")
        return

    async with SessionLocal() as session:
        # reset
        await session.execute(delete(PiiType))
        await session.execute(delete(PiiRiskLevel))
        session.add_all([PiiType(**r) for r in pii_types])
        session.add_all([PiiRiskLevel(**r) for r in risk_levels])
        await session.commit()
        print(f"  적재 완료: pii_types={len(pii_types)}, pii_risk_levels={len(risk_levels)}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="파싱만 하고 DB 미적재")
    args = p.parse_args()
    asyncio.run(load(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
