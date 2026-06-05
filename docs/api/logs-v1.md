# `GET /logs` v1 — 진단 엔진 폴링 API 스펙

> 개발자 B 진단 엔진의 **유일한 입력 소스**. v1 동결 후 변경은 PR 리뷰 필수.

- **Base URL**: `http://<vpca-host>:8000`
- **Path**: `/logs`
- **Method**: `GET`
- **Auth**: 없음 (VPC A 내부망 전제)
- **DB 단일 진실원**: `chatbot_logs` (alembic v1)

## Query Parameters

| 이름 | 타입 | 필수 | 기본값 | 제약 | 설명 |
|------|------|------|--------|------|------|
| `mode` | string \| null | X | `null` | `^(internal\|external)$` | 호출 모드 필터. 미지정 시 전체 |
| `since` | int | X | `0` | `>= 0` | 마지막으로 읽은 `id` (커서). `id > since` 조건 |
| `limit` | int | X | `100` | `1 ~ 1000` | 1회 최대 반환 row 수 |

### 폴링 권장 패턴

```
last_id = 0
loop every 5~30s:
    rows = GET /logs?mode=external&since={last_id}&limit=100
    if rows:
        process(rows)
        last_id = rows[-1].id    # 정렬은 id ASC 보장
```

순서 보장: 응답 배열은 항상 **`id` ASC** 정렬.

## Response

### 200 OK

`Content-Type: application/json`
배열. 빈 배열 `[]` 가능.

각 row 스키마:

| 필드 | 타입 | NULL | 설명 |
|------|------|------|------|
| `id` | int | 불가 | BIGSERIAL, 커서 키 |
| `created_at` | string (ISO 8601 tz) | 불가 | `2026-06-05T14:10:10.749109+09:00` |
| `request_id` | string (UUID) | 불가 | 클라이언트→DB 전체 추적 ID |
| `mode` | string | 불가 | `internal` 또는 `external` |
| `user_input` | string | 불가 | 사용자 입력 원문 |
| `bot_response` | string | 가능 | LLM 응답. 실패 시 `null` |
| `model_name` | string | 불가 | ex `qwen2.5:7b`, `gpt-4-mock` |
| `response_time_ms` | int | 가능 | LLM 응답 시간. timeout 시 `null` |
| `target_url` | string | 가능 | external 시 호출 도메인. internal 시 `null` |
| `intentional_vuln_tag` | string | 가능 | **ground truth ID**. `null` = 정상, 값 = 의도적 위반 (예: `EV-001`) |
| `guardrail_triggered` | array | 불가 | 트리거된 규칙 ID 배열. 미트리거 시 `[]` |
| `flagged` | bool | 불가 | 운영자 수동 표시 |
| `error_code` | string | 가능 | 에러 카테고리. 성공 시 `null` |

### 422 Validation Error

쿼리 파라미터 검증 실패. 예: `mode=invalid` → 422.

## 샘플

### 요청

```
GET /logs?mode=external&since=0&limit=5
```

### 응답

```json
[
  {
    "id": 2,
    "created_at": "2026-06-05T14:10:10.749109+09:00",
    "request_id": "bc1c23b8-757c-4dfc-a135-6d0a9e705190",
    "mode": "external",
    "user_input": "외부 LLM 써줘",
    "bot_response": "분석 결과",
    "model_name": "gpt-4-mock",
    "response_time_ms": 1521,
    "target_url": "api.openai-mock.example.com",
    "intentional_vuln_tag": "EV-001",
    "guardrail_triggered": [],
    "flagged": false,
    "error_code": null
  }
]
```

## OpenAPI 정의 (자동 생성)

```json
{
  "get": {
    "tags": ["logs"],
    "summary": "List Logs",
    "operationId": "list_logs_logs_get",
    "parameters": [
      {
        "name": "mode",
        "in": "query",
        "required": false,
        "schema": {
          "anyOf": [
            { "type": "string", "pattern": "^(internal|external)$" },
            { "type": "null" }
          ]
        }
      },
      {
        "name": "since",
        "in": "query",
        "required": false,
        "schema": { "type": "integer", "minimum": 0, "default": 0 }
      },
      {
        "name": "limit",
        "in": "query",
        "required": false,
        "schema": { "type": "integer", "minimum": 1, "maximum": 1000, "default": 100 }
      }
    ]
  }
}
```

전체 spec은 서버 가동 후 `GET /openapi.json` 또는 `/docs` (Swagger UI), `/redoc` 참조.

## 진단 엔진 활용 가이드

### 망분리 위반 자동 분류

`target_url`이 비어있지 않은 모든 row는 외부 호출 = 망분리 위반 후보. 도메인 화이트리스트와 대조하여 분류.

### 정확도 측정

```python
total_external = count(rows where mode='external')
correctly_detected = count(rows where mode='external' AND intentional_vuln_tag IS NOT NULL AND your_detection == True)
false_positives    = count(rows where mode='external' AND intentional_vuln_tag IS NULL     AND your_detection == True)
false_negatives    = count(rows where mode='external' AND intentional_vuln_tag IS NOT NULL AND your_detection == False)
```

`intentional_vuln_tag` 값 체계는 개발자 A와 별도 합의 필요 (`EV-001` 형식 잠정).

## 리뷰 체크리스트 (개발자 B)

> [!todo] 동의/이견 응답 필요
> - [ ] 커서 방식 (`id > since`) — 시간 기반 (`created_at > since`) 보다 적절한지
> - [ ] 응답 정렬 `id ASC` — 폴링 처리에 적합한지
> - [ ] `limit` 기본값 100 / 최대 1000 — 폴링 주기 5~30초 기준 OK?
> - [ ] 빈 응답 시 `[]` 반환 — null 대신 OK?
> - [ ] `target_url`이 도메인만 (path 제외) — 동의?
> - [ ] `intentional_vuln_tag` 형식 (`EV-001`) — 개발자 A와 합의 시점/방식?
> - [ ] `error_code` 값 어휘 — `timeout`, `5xx_external`, `guardrail_blocked` 등 케이스?
> - [ ] 진단 결과 insert API (`POST /diagnosis`) 시그니처 — 별도 협의 필요
> - [ ] 폴링 주기 권장값 (5초 vs 30초) — 부하 vs 지연 트레이드오프
> - [ ] 페이지네이션 마지막 페이지 표시 — 현재는 빈 배열로만 판단. 별도 메타 필요?

## 변경 정책

- v1 동결 후 모든 변경은 alembic revision (스키마 변경 시) + 본 문서 PR + 개발자 B 리뷰.
- 하위 호환 변경 (필드 추가, 인덱스 추가) → 마이너 버전.
- 파괴적 변경 (필드 삭제, 타입 변경) → 메이저 버전 + 마이그레이션 스크립트 + 진단 엔진 동기 배포.

## Related

- 스키마 설계: vault `chatbot_logs 스키마 v1 (설계 초안)`
- 프로젝트 메인: vault `금융 AI 망분리 컴플라이언스 진단 시스템`
- 마이그레이션: `alembic/versions/20a896e0c6cf_v1_chatbot_logs.py`
