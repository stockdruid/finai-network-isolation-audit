# 챗봇 ↔ 컴플라이언스 JSONL 브릿지 (v5)

**대상:** 개발자 A (챗봇, `msj1613/finance-compliance-chatbot`)
**발신:** 개발자 C (백엔드/DB, `stockdruid/finai-network-isolation-audit`)
**작성일:** 2026-07-07
**전제:** 우리 DB 스키마 v5 (alembic `d2a1b8f4e6c3`)

---

## 1. 목적

두 시스템은 각자 자체 Postgres + FastAPI + Streamlit을 운영한다. 발표에서는 챗봇의 실 로그가 우리 컴플라이언스 대시보드에 반영되어 **PII 위험도 실시간 판정 + ISMS-P 매트릭스**를 시연한다.

DB 공유 대신 **JSONL 브릿지** 방식을 택했다. 이유:
- 챗봇 팀 조율 최소 (그쪽은 이미 `logs/chatbot.jsonl` 실시간 sink 있음)
- 우리 스키마만 v5로 확장하면 됨 (자기 통제 가능)
- 발표 실패 시 fallback 쉬움 (JSONL 파일이 유실돼도 DB export로 재생성 가능)

---

## 2. 데이터 흐름

```
[챗봇 시스템 (A)]
  ├── logs/chatbot.jsonl              # 실시간 append (dual sink)
  └── scripts/export_logs.py           # 배치 export (전체 덤프)
             │
             ▼  (JSONL 파일 복사)
[컴플라이언스 시스템 (C)]
  └── scripts/import_chatbot_logs.py --path <A>/logs/chatbot_export.jsonl --reset
             │
             ▼
  chatbot_logs 테이블 (v5) — client_ip / user_id / tool_name 포함
             │
             ▼
  대시보드 + PII 위험도 aggregate + ISMS-P 판정 매핑
```

---

## 3. 챗봇 → 컴플라이언스 필드 매핑 (v5)

| A 챗봇 (`ChatbotLogOut`) | 컴플라이언스 (`chatbot_logs`) | 비고 |
|---|---|---|
| `id` (UUID 문자열) | (스킵) | 우리 `id`는 BigInteger autoincrement |
| `conversation_id` | `conversation_id` (PG UUID) | 동일 |
| `request_id` | `request_id` (PG UUID) | 동일, 원본 UUID 보존 |
| `created_at` | `created_at` (TIMESTAMP tz) | ISO 8601 파싱 |
| `event_type` | `event_type` | chat / signup / login |
| **`client_ip`** | **`client_ip`** (v5) | DDoS 추적 |
| **`user_id`** | **`user_id`** (v5) | 인증 세션 식별 |
| **`tool_name`** | **`tool_name`** (v5) | 컴포넌트 식별 |
| `mode` | `mode` | internal / external |
| `target_url` | `target_url` | |
| `target_provider` | `target_provider` | |
| `user_prompt` | `user_input` | 필드명만 변환 |
| `rag_context` | `rag_context` | |
| `llm_response` | `bot_response` | 필드명만 변환 |
| `latency_ms` | `response_time_ms` | 필드명만 변환 |
| `status` | `status` | success / blocked / error |
| `error_detail` | `error_detail` | |
| `guardrail_triggered` (str) | `guardrail_triggered` (JSONB list) | 스트링을 `[val]`로 감쌈 |
| `intentional_vuln_tag` | `intentional_vuln_tag` | EV-001 / EV-002 / EV-003 |
| `pii_detected` | `pii_detected` | |
| `pii_fields` | `pii_fields` | 리스트, PII 정규화 리졸버가 정본 매핑 |
| `security_signals` | `security_signals` | JSONB 그대로 |
| `raw_request` | `raw_request` | JSONB |
| `raw_response` | `raw_response` | JSONB |

**우리 스키마에만 있고 A에 없는 필드** (임포터가 자동으로 None 처리):
- `model_name`, `error_code`, `flagged`

---

## 4. 브릿지 실행 절차

### 4.1 A 챗봇 측 (로그 export)

```bash
cd <chatbot repo>
PYTHONPATH=. uv run python scripts/export_logs.py logs/chatbot_export.jsonl
# → exported N logs → logs/chatbot_export.jsonl
```

### 4.2 우리 측 (임포트)

```bash
cd <finai-compliance repo>

# 최초 1회: v5 마이그레이션 (chatbot_logs에 client_ip/user_id/tool_name 컬럼 추가)
alembic upgrade head

# 임포트 (기존 로그 대체)
python scripts/import_chatbot_logs.py --path <chatbot_repo>/logs/chatbot_export.jsonl --reset
```

### 4.3 실시간 브릿지 (선택)

발표 데모용 지속 sync가 필요하면 A의 `logs/chatbot.jsonl` (실시간 append)를 감시하는 `watchdog` 스크립트를 붙일 수 있다 (7/13 리허설 전 결정).

---

## 5. 발표 시나리오

1. A의 챗봇 UI에서 EV-001~003 시나리오 3건 시연 (외부 LLM 호출 / PII 노출 / 프롬프트 인젝션)
2. 챗봇이 `logs/chatbot.jsonl`에 실시간 append
3. `scripts/export_logs.py` 실행 → 최신 export
4. 우리 임포터로 pull → chatbot_logs v5 갱신
5. **우리 대시보드 Hero 밴드**가 실시간 위험도 재산정:
   - PII 필드 정규화 (ssn/customer_name/phone/email → 정본)
   - 합산 위험도 → **Critical 등급 판정** (30점 이상)
6. **ISMS-P 판정 페이지**에서 진단 엔진(B)이 배치 verdict 반영

---

## 6. 실패 모드 & 대응

| 실패 | 원인 | 대응 |
|---|---|---|
| `parseTimestamp: NaT` | `created_at` 포맷 미스매치 | ISO 8601 `2026-07-07T18:30:00+09:00` 형식 검증 |
| `client_ip is None` | A 챗봇이 X-Forwarded-For 못 읽음 | ALB/nginx `X-Forwarded-For` 설정 or 임포터가 None 허용 |
| PII 정규화 실패 (`unmatched`) | A가 신규 라벨 사용 | `core/pii_resolver.py` ALIASES 사전에 추가 후 재임포트 |
| `intentional_vuln_tag`가 다른 명명 | A가 EV 태그 규약 변경 | 팀 회의 필요 |

---

## 7. 스키마 안정성

- **v5 동결** — 발표(7/14)까지 필드 추가 없음
- **필드 추가 프로세스**: A가 신규 필드 필요 시 사전 공유 → 우리 v6 마이그레이션 → PR 리뷰
- **컬럼명 통일 여부** (`user_prompt` vs `user_input` 등): 발표 후 v6에서 재검토 (지금은 임포터 매핑으로 커버)

---

## 8. 관련 문서

- `docs/api/b-integration-v4.md` — 진단 엔진(B) 통합 계약
- `docs/api/logs-v1.md` — `GET /logs` 폴링 계약 (v1)
- `scripts/integration_test.py` — 계약 검증 참조 스크립트
