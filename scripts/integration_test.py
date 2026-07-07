"""개발자 B 통합 참조 스크립트 — 진단 엔진 폴링 사이클 시뮬레이션.

`docs/api/b-integration-v4.md`의 계약을 실제 실행 가능한 코드로 검증한다.
개발자 B는 이 스크립트를 참조해 자신의 진단 엔진을 구현하면 된다.

동작:
  1. GET /health              — API 살아있는지 확인
  2. GET /logs                — 챗봇 로그 폴링 (진단 대상)
  3. POST /pii-risk/score     — 로그별 PII 위험도 산정
  4. GET /pii-risk/aggregate  — 전체 챗봇 로그 위험도 집계
  5. GET /isms-p/checklist    — 판정할 세부 점검항목 조회
  6. POST /isms-p/checklist/bulk-verdict — Mock detector 결과 배치 반영
  7. GET /isms-p/summary/verdict — 판정 집계 확인
  8. (선택) --reset 시 미평가로 baseline 복원

Usage:
    python scripts/integration_test.py                 # 통합 테스트 실행
    python scripts/integration_test.py --reset         # 실행 후 baseline 복원
    FASTAPI_BASE_URL=http://api:8000 python scripts/integration_test.py  # 도커 내부
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import httpx

API = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")
TIMEOUT = 10.0


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------

def check(desc: str, cond: bool, actual: object = None) -> None:
    """Assertion + 표준 출력. False면 즉시 exit 1."""
    if cond:
        print(f"  ✓ {desc}")
    else:
        print(f"  ✗ {desc}  (got: {actual!r})")
        sys.exit(1)


@dataclass
class MockDetectorResult:
    """Mock 진단 엔진 출력. 개발자 B의 실제 로직 자리."""

    detector_id: str
    passed: bool
    reason: str


def mock_detect(log: dict) -> list[MockDetectorResult]:
    """샘플 판정 로직 — 실 로그의 signal 필드 참조.

    개발자 B가 여기에 자신의 Detector 엔진 결과를 넣는다.
    """
    results: list[MockDetectorResult] = []
    signals = log.get("security_signals") or {}
    pii_detected = bool(log.get("pii_detected"))
    mode = log.get("mode")

    # 예시 규칙:
    # 1) mode=external + PII 있으면 DET-CHAT-PI-001 FAIL
    # 2) status=blocked 이면 가드레일 통과 → DET-CHAT-SAFETY PASS
    # 3) 그 외 정보성 PASS
    if mode == "external" and pii_detected:
        results.append(MockDetectorResult("DET-CHAT-PI-001", False, "external + PII"))
    elif log.get("status") == "blocked":
        results.append(MockDetectorResult("DET-CHAT-SAFETY-001", True, "blocked by guardrail"))
    else:
        results.append(MockDetectorResult("DET-CHAT-BASELINE", True, "no violations"))
    return results


# ---------------------------------------------------------------------------
# 단계별 실행
# ---------------------------------------------------------------------------

def step_health(client: httpx.Client) -> None:
    print("\n[1/7] GET /health")
    r = client.get(f"{API}/health")
    check("200 응답", r.status_code == 200, r.status_code)
    check("status ok", r.json().get("status") == "ok", r.json())


def step_fetch_logs(client: httpx.Client) -> list[dict]:
    print("\n[2/7] GET /logs (진단 대상 로그 폴링)")
    r = client.get(f"{API}/logs", params={"limit": 50})
    check("200 응답", r.status_code == 200, r.status_code)
    logs = r.json()
    check("로그 배열 반환", isinstance(logs, list), type(logs).__name__)
    check("최소 1건 이상", len(logs) > 0, len(logs))
    print(f"    → 로그 {len(logs)}건 수신 (샘플 id={logs[0]['id']}, mode={logs[0]['mode']})")
    return logs


def step_score_each_log(client: httpx.Client, logs: list[dict]) -> None:
    print("\n[3/7] POST /pii-risk/score (로그별 PII 위험도)")
    scored = 0
    for lg in logs:
        fields = lg.get("pii_fields") or []
        if not fields:
            continue
        r = client.post(f"{API}/pii-risk/score", json={"fields": fields})
        check(f"log_id={lg['id']} score 200", r.status_code == 200, r.status_code)
        data = r.json()
        # 계약 검증
        for key in ("matched", "unmatched", "resolved_map", "total_score", "level"):
            check(f"응답에 '{key}' 포함", key in data, list(data.keys()))
        scored += 1
        # 처음 3건만 상세 출력
        if scored <= 3:
            lvl = data["level"]["level_en"] if data["level"] else None
            print(
                f"    → log_id={lg['id']} fields={fields} → "
                f"score={data['total_score']} level={lvl} unmatched={data['unmatched']}"
            )
    print(f"    총 {scored}건 스코어링 완료")


def step_aggregate(client: httpx.Client) -> None:
    print("\n[4/7] GET /pii-risk/aggregate (전체 위험도)")
    r = client.get(f"{API}/pii-risk/aggregate")
    check("200 응답", r.status_code == 200, r.status_code)
    data = r.json()
    for key in ("pii_log_count", "total_score", "level", "by_type", "unmatched"):
        check(f"응답에 '{key}' 포함", key in data, list(data.keys()))
    lvl = data["level"]["level_en"] if data["level"] else None
    print(
        f"    → 로그 {data['pii_log_count']}건 · "
        f"합산 {data['total_score']}점 · 등급 {lvl} · "
        f"유형 {len(data['by_type'])}종 · 미분류 {len(data['unmatched'])}건"
    )


def step_fetch_checklist(client: httpx.Client) -> list[dict]:
    print("\n[5/7] GET /isms-p/checklist (판정 대상 조회)")
    r = client.get(f"{API}/isms-p/checklist", params={"limit": 10})
    check("200 응답", r.status_code == 200, r.status_code)
    items = r.json()
    check("배열 반환", isinstance(items, list), type(items).__name__)
    check("10건 이내", len(items) <= 10, len(items))
    return items


def step_bulk_verdict(
    client: httpx.Client, logs: list[dict], items: list[dict]
) -> None:
    print("\n[6/7] POST /isms-p/checklist/bulk-verdict (Mock detector 결과 반영)")
    # Mock: 로그별 detector 실행, 결과를 앞 10개 checklist 항목에 순환 매핑
    if not items:
        print("    checklist 항목 없음 → 스킵")
        return

    updates: list[dict] = []
    for i, lg in enumerate(logs[: len(items)]):
        det_results = mock_detect(lg)
        item = items[i]
        # 하나의 로그에 여러 detector 결과가 나올 수 있음 — 첫 결과만 반영 (샘플)
        first = det_results[0]
        verdict = "적합" if first.passed else "부적합"
        updates.append(
            {
                "item_id": item["id"],
                "verdict": verdict,
                "review_memo": f"auto: {first.detector_id} {'pass' if first.passed else 'fail'} - {first.reason}",
                "responsible": "diagnosis-engine-mock",
            }
        )

    # 의도적 잘못된 값 추가 → skipped 검증
    updates.append({"item_id": 999999, "verdict": "적합"})
    updates.append({"item_id": items[0]["id"], "verdict": "INVALID_VERDICT"})

    r = client.post(f"{API}/isms-p/checklist/bulk-verdict", json={"updates": updates})
    check("200 응답", r.status_code == 200, r.status_code)
    data = r.json()
    for key in ("updated", "skipped", "total"):
        check(f"응답에 '{key}' 포함", key in data, list(data.keys()))

    check(
        "skipped에 not found 포함",
        any(s.get("reason") == "not found" for s in data["skipped"]),
        data["skipped"],
    )
    check(
        "skipped에 invalid verdict 포함",
        any("invalid verdict" in s.get("reason", "") for s in data["skipped"]),
        data["skipped"],
    )
    print(
        f"    → total={data['total']}, updated={len(data['updated'])}, "
        f"skipped={len(data['skipped'])}"
    )


def step_verdict_summary(client: httpx.Client) -> None:
    print("\n[7/7] GET /isms-p/summary/verdict (판정 집계 확인)")
    r = client.get(f"{API}/isms-p/summary/verdict")
    check("200 응답", r.status_code == 200, r.status_code)
    data = r.json()
    check("배열 반환", isinstance(data, list), type(data).__name__)
    for row in data:
        print(f"    → {row['verdict']}: {row['count']}건")


def step_reset_baseline(client: httpx.Client) -> None:
    print("\n[reset] baseline 복원 (모든 verdict → 미평가)")
    # 갱신된 항목 전부 조회 → 미평가로 되돌림
    total_reset = 0
    for verdict in ("적합", "부적합", "부분적합", "증적부족", "적용제외"):
        r = client.get(
            f"{API}/isms-p/checklist",
            params={"verdict": verdict, "limit": 500},
        )
        items = r.json()
        if not items:
            continue
        updates = [
            {"item_id": it["id"], "verdict": "미평가", "review_memo": ""} for it in items
        ]
        r2 = client.post(
            f"{API}/isms-p/checklist/bulk-verdict", json={"updates": updates}
        )
        total_reset += len(r2.json().get("updated", []))
    print(f"    → {total_reset}건 미평가로 복원")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true", help="테스트 후 baseline 복원")
    p.add_argument("--no-write", action="store_true", help="읽기만 (bulk-verdict 스킵)")
    args = p.parse_args()

    print(f"=== finai-compliance 통합 테스트 (API={API}) ===")

    with httpx.Client(timeout=TIMEOUT) as client:
        step_health(client)
        logs = step_fetch_logs(client)
        step_score_each_log(client, logs)
        step_aggregate(client)
        items = step_fetch_checklist(client)
        if not args.no_write:
            step_bulk_verdict(client, logs, items)
        step_verdict_summary(client)
        if args.reset:
            step_reset_baseline(client)
            step_verdict_summary(client)

    print("\n✅ 통합 테스트 통과")


if __name__ == "__main__":
    main()
