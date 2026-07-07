# 진단 엔진 ↔ 컴플라이언스 백엔드 통합 계약 (v4)

**대상:** 개발자 B (진단 엔진)
**발신:** 개발자 C (백엔드/DB)
**Base URL:** `http://<host>:8000` (로컬 개발) · AWS 이전 시 갱신
**작성일:** 2026-07-07
**스키마 버전:** v4 (alembic `c9e7d3a5f011`)

---

## 1. 목적

진단 엔진(개발자 B)이 챗봇 로그를 폴링해 위반을 탐지한 결과를 다음 3개 방향으로 백엔드에 반영한다:

1. **`diagnosis_results` 인서트** — 개별 위반 판정 (기존, Phase 1)
2. **`isms_p_checklist_items.verdict` 업데이트** — 인증기준 세부 항목 판정 (v4 신규)
3. **PII 위험도 스코어링 호출** — 챗봇 로그 `pii_fields` → 위험도 점수 산정 (v4 신규)

이 문서는 신규 v4 계약 위주. 기존 Phase 1 계약(`GET /logs`, `POST /diagnosis`)은 [logs-v1.md](./logs-v1.md) 참조.

---

## 2. 데이터 흐름

```
[챗봇 A] ───write───▶ chatbot_logs ◀───poll GET /logs─── [진단 엔진 B]
                                                              │
                                     [B 자체 판정 로직]
                                          │
             ┌────────────────────┬───────┴────────┬───────────────────┐
             ▼                    ▼                ▼                   ▼
   POST /diagnosis     POST /pii-risk/score   PATCH /isms-p/       POST /isms-p/
   (기존)              (선택)                  checklist/{id}       checklist/
                                                                    bulk-verdict
                                                                    (배치 권장)
```

---

## 3. 신규 엔드포인트

### 3.1 `POST /pii-risk/score` — 개별 로그 PII 위험도 산정

로그 하나의 `pii_fields`(자유 라벨)를 정본 명칭으로 정규화 후 합산 위험도 + 등급 반환.

**요청**
```json
{"fields": ["ssn", "email", "customer_name"]}
```

**응답 200**
```json
{
  "matched": [
    {"name": "주민등록번호", "risk_score": 10.0, "legal_basis": "..."},
    {"name": "이메일",       "risk_score": 1.6,  "legal_basis": "..."},
    {"name": "이름",         "risk_score": 1.6,  "legal_basis": "..."}
  ],
  "unmatched": [],
  "resolved_map": {"ssn": "주민등록번호", "email": "이메일", "customer_name": "이름"},
  "total_score": 13.2,
  "level": {
    "level_ko": "중간", "level_en": "Medium",
    "score_range": "10 ~ 19점", "action_level": "조치 필요"
  }
}
```

**등급 기준** — Critical ≥30 / High 20~29 / Medium 10~19 / Low <10

**정규화 지원 라벨** — [`core/pii_resolver.py`](../../core/pii_resolver.py) 참조. 매칭 실패 시 `unmatched` 배열로 반환 (스코어 0). 필요 시 개발자 C에게 별칭 추가 요청.

---

### 3.2 `PATCH /isms-p/checklist/{item_id}` — 개별 판정 업데이트

**요청** (모든 필드 optional, None은 미변경)
```json
{
  "verdict": "적합",
  "review_memo": "auto: DET-CHAT-PI-001 pass",
  "evidence_location": "logs/2026-07-08/chatbot_logs.jsonl#L42",
  "responsible": "diagnosis-engine",
  "remediation_due": null
}
```

**응답 200** — 업데이트된 `IsmsPChecklistItem` 전체
```json
{
  "id": 42, "criterion_id": "2.7.1", "check_number": 3,
  "verdict": "적합", "review_memo": "auto: DET-CHAT-PI-001 pass",
  ...
}
```

**verdict 화이트리스트** — `미평가` / `적합` / `부분적합` / `부적합` / `증적부족` / `적용제외`
- 그 외 값 → **400 Bad Request** (`{"detail": "Invalid verdict: ...", "allowed": [...]}`)
- `item_id` 미존재 → **404 Not Found**
- DB 쓰기 실패 → **503 Service Unavailable** (Fail-Loud 정책)

---

### 3.3 `POST /isms-p/checklist/bulk-verdict` — **배치 판정 (권장)**

진단 엔진이 한 사이클에 여러 항목을 업데이트할 때 이걸 써라. **부분 성공 허용**.

**요청**
```json
{
  "updates": [
    {"item_id": 42, "verdict": "적합",   "review_memo": "auto: DET-CHAT-PI-001 pass"},
    {"item_id": 43, "verdict": "부적합", "review_memo": "auto: pattern LLM02"},
    {"item_id": 99, "verdict": "적합"}
  ]
}
```

**응답 200**
```json
{
  "total": 3,
  "updated": [
    {"item_id": 42, "verdict": "적합"},
    {"item_id": 43, "verdict": "부적합"}
  ],
  "skipped": [
    {"reason": "not found", "item_id": 99}
  ]
}
```

**skipped 사유**
- `"missing item_id"` — 페이로드에 `item_id` 누락
- `"invalid verdict: <값>"` — 화이트리스트 위반
- `"not found"` — `item_id`가 DB에 없음

---

### 3.4 조회 API (참고)

- **`GET /isms-p/criteria`** — 48 인증기준 (major_category / section_id 필터)
- **`GET /isms-p/checklist?criterion_id=2.7.1`** — 인증기준별 세부 항목 리스트
- **`GET /isms-p/summary/verdict`** — 판정별 집계 (진단 커버리지 대시보드용)
- **`GET /pii-risk/aggregate?limit=1000`** — 챗봇 로그 전체 → 정규화 → 합산 등급 (진단 엔진 KPI로 참조 가능)

---

## 4. Detector ↔ Checklist 매핑 (개발자 B 담당)

`detectors.reference_standards`(JSONB 배열)에 관련 인증기준 ID를 포함할 것.

**권장 포맷:**
```json
["ISMS-P:2.7.1", "ISMS-P:2.10.4", "OWASP:LLM02", "GAI-2.4"]
```

- **`ISMS-P:<criterion_id>`** 프리픽스가 있는 항목만 자동 매핑 후보로 사용
- 진단 엔진에서 Detector 실행 결과를 판정으로 변환 시:
  - PASS → `verdict="적합"`, `review_memo=f"auto: {detector_id} pass"`
  - FAIL → `verdict="부적합"`, `review_memo=f"auto: {detector_id} {failure_reason}"`
  - 증적 부족 → `verdict="증적부족"`

**한 인증기준 = 여러 세부 점검항목:** 각 점검항목의 `check_number`를 명세에 포함해 세부 매핑. 매핑 안 되는 세부 항목은 사람이 수동 판정 (Streamlit UI).

---

## 5. End-to-End 워크플로우 예시

### 5.1 진단 엔진 폴링 사이클

```python
# 진단 엔진 (개발자 B)
async def diagnose_cycle():
    logs = await http.get(f"{API}/logs?since={cursor}&limit=100")
    for log in logs:
        # 1. PII 위험도 산정
        if log["pii_fields"]:
            pii = await http.post(f"{API}/pii-risk/score", json={"fields": log["pii_fields"]})
            # pii["total_score"], pii["level"]

        # 2. Detector 실행 → 위반 판정
        violations = run_detectors(log)
        for v in violations:
            await http.post(f"{API}/diagnosis", json={
                "source_log_id": log["id"],
                "violation_type": v.type,
                "severity": v.severity,
                "regulation_reference": v.refs,
                "correct": (log["intentional_vuln_tag"] == v.type),
            })

    # 3. Detector 실행 배치 결과 → ISMS-P 판정 반영
    verdict_updates = []
    for det_result in aggregate_detector_results():
        for isms_id in det_result.mapped_isms_ids:  # ["2.7.1#3", "2.10.4#1"]
            criterion_id, check_no = isms_id.split("#")
            item = await http.get(f"{API}/isms-p/checklist?criterion_id={criterion_id}")
            target = next(x for x in item if x["check_number"] == int(check_no))
            verdict_updates.append({
                "item_id": target["id"],
                "verdict": "적합" if det_result.pass_ else "부적합",
                "review_memo": f"auto: {det_result.detector_id} {'pass' if det_result.pass_ else 'fail'}",
            })

    if verdict_updates:
        await http.post(f"{API}/isms-p/checklist/bulk-verdict", json={"updates": verdict_updates})

    cursor = max(l["id"] for l in logs) if logs else cursor
```

---

## 6. 에러 처리 규약

| 코드 | 상황 | 진단 엔진 대응 |
|------|------|----------------|
| 200  | 정상 | 진행 |
| 400  | verdict 화이트리스트 위반 / 페이로드 스키마 오류 | 로그 남기고 스킵. 재시도 X |
| 404  | 대상 리소스 없음 (item_id 미존재 등) | 로그 남기고 다음 항목 |
| 422  | Pydantic 검증 실패 | 스키마 확인 후 수정 |
| 503  | DB write 실패 (Fail-Loud) | **재시도 (exponential backoff, max 3회)**. 계속 실패 시 진단 사이클 중단 + 알림 |
| 5xx  | 그 외 | 동일하게 backoff 재시도 |

**Idempotency:** PATCH / bulk-verdict는 멱등. 같은 페이로드 여러 번 호출해도 결과 동일.

---

## 7. 스키마 안정성 & 변경 정책

- **v4 스키마 동결** — 발표(2026-07-14)까지 필드 추가·변경 없음
- 필드 추가는 nullable로만 진행 → 기존 클라이언트 안전
- **Breaking change** 필요 시 최소 24시간 전 사전 공유 + PR 리뷰
- alembic 마이그레이션 변경은 반드시 개발자 C 리뷰

---

## 8. 로컬 개발 환경

```bash
# DB + FastAPI + Streamlit 부팅
cd finai-compliance
alembic upgrade head
python scripts/import_compliance_mappings.py
python scripts/import_pii_risk.py
python scripts/import_isms_p.py
python scripts/import_chatbot_logs.py --reset  # 실 로그 16건

uvicorn main:app --port 8000
# Swagger UI: http://localhost:8000/docs
```

**진단 엔진 개발 중 baseline 리셋:**
```bash
python scripts/import_isms_p.py  # verdict 모두 미평가로 복원
```

---

## 9. 문의 / 이슈

- 별칭 사전 추가 요청: `core/pii_resolver.py` PR + 개발자 C 리뷰
- 신규 인증기준 필요: 정책팀 자료 갱신 필요, 개발자 C가 v5 마이그레이션 관리
- 성능 이슈 (폴링 부하 등): `GET /logs` 페이지네이션 커서 활용, 필요 시 인덱스 튜닝 요청
