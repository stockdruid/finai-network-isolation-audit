"""개발자 B 진단 결과 JSON → 우리 컴플라이언스 시스템 브릿지.

B의 진단 엔진이 만든 dia_result.json 형식:
    {
        "status": "success",
        "total_violations": 8,
        "data": [
            {
                "log_index": 1,           # 1-based 순서 (DB id 아님)
                "event_type": "chat",
                "user_prompt": "...",
                "target_url": "...",
                "violations": ["망분리 위반 (SSRF)", "HTTP 평문", ...],
                "policy_mappings": ["전자금융감독규정 제15조 ...", "ISMS-P 2.7.1 ..."]
            },
            ...
        ]
    }

두 갈래로 반영한다:
  1) POST /diagnosis  ← 각 violation을 diagnosis_results에 개별 insert
  2) POST /isms-p/checklist/bulk-verdict  ← policy_mappings에서 `ISMS-P X.Y.Z`
     정규식으로 추출해 해당 인증기준의 세부 점검항목 전체를 verdict=부적합 처리

가정:
  - B의 `log_index`는 chatbot_logs를 `id ASC`로 정렬했을 때의 1-based 순번
  - 우리 chatbot_logs가 B가 진단한 로그 셋과 동일해야 함 (dia_result.json 생성 시점 기준)

Usage:
    python scripts/import_diagnosis_result.py --path <경로>          # 실 반영
    python scripts/import_diagnosis_result.py --path <경로> --dry-run  # 파싱만
    python scripts/import_diagnosis_result.py --path <경로> --isms-only # ISMS-P 판정만
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from db.models import ChatbotLog, IsmsPChecklistItem
from db.session import SessionLocal


API = "http://localhost:8000"
ISMS_PATTERN = re.compile(r"ISMS-P\s*(\d+\.\d+\.\d+)")


def infer_severity(violations: list[str]) -> str:
    """위반 텍스트에서 심각도 추정. B가 severity 제공 안 하므로 키워드 기반."""
    joined = " ".join(violations).lower()
    if any(k in joined for k in ["ssrf", "인젝션", "평문 유출", "고유식별", "idor", "인가"]):
        return "critical"
    if any(k in joined for k in ["평문 저장", "평문 통신", "노출", "유출"]):
        return "high"
    if any(k in joined for k in ["장문", "자원", "ddos", "남용"]):
        return "medium"
    return "high"


def extract_isms_ids(policy_mappings: list[str]) -> list[str]:
    """policy_mappings 배열에서 ISMS-P criterion_id 추출."""
    ids: set[str] = set()
    for mapping in policy_mappings:
        for m in ISMS_PATTERN.finditer(mapping):
            ids.add(m.group(1))
    return sorted(ids)


async def resolve_log_ids(log_indexes: list[int]) -> dict[int, int]:
    """B의 log_index (1-based) → 우리 chatbot_logs.id 매핑.

    챗봇 로그를 id ASC로 정렬해 순번을 매긴다.
    """
    async with SessionLocal() as session:
        stmt = select(ChatbotLog).order_by(ChatbotLog.id.asc())
        result = await session.execute(stmt)
        all_logs = list(result.scalars().all())

    idx_to_id: dict[int, int] = {}
    for li in log_indexes:
        if 1 <= li <= len(all_logs):
            idx_to_id[li] = all_logs[li - 1].id
    return idx_to_id


async def collect_checklist_item_ids(
    criterion_ids: list[str],
) -> dict[str, list[int]]:
    """criterion_id 목록 → 각 criterion의 checklist_items id 목록."""
    if not criterion_ids:
        return {}
    async with SessionLocal() as session:
        stmt = select(IsmsPChecklistItem).where(
            IsmsPChecklistItem.criterion_id.in_(criterion_ids)
        )
        result = await session.execute(stmt)
        items = list(result.scalars().all())
    out: dict[str, list[int]] = {}
    for it in items:
        out.setdefault(it.criterion_id, []).append(it.id)
    return out


def build_diagnosis_payloads(
    entries: list[dict], idx_to_id: dict[int, int]
) -> list[dict]:
    """각 entry의 violations를 개별 POST /diagnosis 페이로드로 확장."""
    payloads: list[dict] = []
    for entry in entries:
        li = entry.get("log_index")
        source_log_id = idx_to_id.get(li)
        if source_log_id is None:
            print(f"  [skip] log_index={li} 매핑 실패")
            continue
        violations: list[str] = entry.get("violations", []) or []
        policy_mappings: list[str] = entry.get("policy_mappings", []) or []
        severity = infer_severity(violations)
        for i, v in enumerate(violations):
            regulation = (
                policy_mappings[i] if i < len(policy_mappings) else policy_mappings
            )
            payloads.append(
                {
                    "source_log_id": source_log_id,
                    "violation_type": v,
                    "severity": severity,
                    "matched_target_url": entry.get("target_url"),
                    "regulation_reference": {
                        "policy_mappings": policy_mappings,
                        "matched_index": i,
                        "matched_ref": regulation,
                    },
                }
            )
    return payloads


def build_isms_updates(
    entries: list[dict], criterion_to_items: dict[str, list[int]]
) -> list[dict]:
    """entries의 policy_mappings에서 ISMS-P ID 추출 후 각 checklist 항목을 부적합 처리."""
    updates_by_item: dict[int, str] = {}
    memo_by_item: dict[int, list[str]] = {}

    for entry in entries:
        criterion_ids = extract_isms_ids(entry.get("policy_mappings", []) or [])
        violation_summary = "; ".join((entry.get("violations") or [])[:2])
        for cid in criterion_ids:
            for item_id in criterion_to_items.get(cid, []):
                updates_by_item[item_id] = "부적합"
                memo_by_item.setdefault(item_id, []).append(
                    f"log#{entry.get('log_index')}: {violation_summary}"
                )

    return [
        {
            "item_id": item_id,
            "verdict": verdict,
            "responsible": "diagnosis-engine-B",
            "review_memo": "\n".join(memo_by_item.get(item_id, [])),
        }
        for item_id, verdict in updates_by_item.items()
    ]


async def load(path: Path, dry_run: bool, isms_only: bool) -> None:
    if not path.exists():
        raise FileNotFoundError(f"진단 결과 파일 없음: {path}")

    print(f"[읽기] {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    entries: list[dict] = doc.get("data", [])
    print(
        f"  status={doc.get('status')}, total_violations={doc.get('total_violations')}, entries={len(entries)}"
    )

    # 1) log_index → source_log_id 매핑
    log_indexes = sorted({e.get("log_index") for e in entries if e.get("log_index")})
    idx_to_id = await resolve_log_ids(log_indexes)
    print(f"  로그 매핑: {len(idx_to_id)}/{len(log_indexes)}건 (log_index → chatbot_logs.id)")
    for li in log_indexes:
        print(f"    log_index={li:2d} → id={idx_to_id.get(li, '?')}")

    # 2) ISMS-P criterion 추출 → checklist_items 조회
    all_criterion_ids = sorted(
        {
            cid
            for e in entries
            for cid in extract_isms_ids(e.get("policy_mappings", []) or [])
        }
    )
    criterion_to_items = await collect_checklist_item_ids(all_criterion_ids)
    print(f"  ISMS-P 추출: {len(all_criterion_ids)}개 인증기준")
    for cid in all_criterion_ids:
        n = len(criterion_to_items.get(cid, []))
        print(f"    {cid} → 세부 점검항목 {n}건")

    diagnosis_payloads = build_diagnosis_payloads(entries, idx_to_id)
    isms_updates = build_isms_updates(entries, criterion_to_items)

    print(f"\n  생성됨: diagnosis {len(diagnosis_payloads)}건, ISMS-P 판정 {len(isms_updates)}건")

    if dry_run:
        print("\n[dry-run] API 미호출. 샘플:")
        for p in diagnosis_payloads[:2]:
            print(f"    diagnosis: {p}")
        for u in isms_updates[:2]:
            print(f"    isms-p:    {u}")
        return

    # 3) API 호출
    with httpx.Client(timeout=15.0) as client:
        if not isms_only:
            posted = 0
            for p in diagnosis_payloads:
                r = client.post(f"{API}/diagnosis", json=p)
                if r.status_code < 300:
                    posted += 1
                else:
                    print(f"    [warn] diagnosis 실패 {r.status_code}: {r.text[:150]}")
            print(f"  ✓ diagnosis POST 완료: {posted}/{len(diagnosis_payloads)}")

        if isms_updates:
            r = client.post(
                f"{API}/isms-p/checklist/bulk-verdict", json={"updates": isms_updates}
            )
            if r.status_code < 300:
                data = r.json()
                print(
                    f"  ✓ ISMS-P bulk-verdict: total={data['total']}, "
                    f"updated={len(data['updated'])}, skipped={len(data['skipped'])}"
                )
            else:
                print(f"    [warn] bulk-verdict 실패 {r.status_code}: {r.text[:150]}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--path", type=Path, required=True, help="진단 결과 JSON 경로")
    p.add_argument("--dry-run", action="store_true", help="파싱만, API 미호출")
    p.add_argument(
        "--isms-only",
        action="store_true",
        help="POST /diagnosis 스킵, ISMS-P 판정만 반영",
    )
    args = p.parse_args()
    asyncio.run(load(args.path, args.dry_run, args.isms_only))


if __name__ == "__main__":
    main()
