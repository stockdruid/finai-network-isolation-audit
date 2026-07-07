# finai-network-isolation-audit

금융권 AI **망분리 위반 시나리오 자동 탐지** 컴플라이언스 진단 시스템.
구름 파이널 프로젝트 (Q2 2026).

## 아키텍처 개요

**VPC A — 내부망 시뮬레이션**

- Streamlit UI (채팅·모드 토글·로그 미리보기)
- FastAPI 단일 앱:
  - `POST /chat` → `core/guardrails` (PII) → `rag/retrieve` (top-k) → `llm/router` (mode 분기) → `db/repository` (Fail-Loud)
  - `GET /logs?mode=external` (진단 엔진 폴링용)
  - `GET /health`
- Ollama (EEVE-Korean / llama3.1)
- Chroma + `ko-sroberta` 임베딩
- **PostgreSQL `chatbot_logs` v1** (alembic 보호, 단일 진실원)

**VPC B — 외부망 시뮬레이션**

- Mock External LLM (`api.openai-mock.example.com`) — EV-001 위반 시나리오

진단 엔진(개발자 B)이 `GET /logs?mode=external` 5~30초 폴링, `target_url` 도메인 검증, `intentional_vuln_tag`로 정확도 측정, 망분리 위반 자동 분류 + 규제 매핑.

## 셋업

### Python (Python 3.12 권장)

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # macOS/Linux
pip install -r requirements-dev.txt
```

### 환경 변수

```bash
copy .env.example .env           # Windows
# cp .env.example .env           # macOS/Linux
# .env 편집 (DB / Ollama / API 키)
```

### 실행 — 두 가지 방법

**A. Docker compose 통합 실행 (팀 표준, 발표/AWS 이전 권장)**

한 번에 `postgres + migrate + api + ui` 부팅. migrate가 alembic upgrade 후 api/ui가 순차 기동.

```bash
docker compose up --build -d
# → api:8000, ui:8501, postgres:5432

# 컴플라이언스 자료 적재 (컨테이너 내부에서)
docker compose exec api python scripts/import_compliance_mappings.py
docker compose exec api python scripts/import_pii_risk.py
docker compose exec api python scripts/import_isms_p.py
docker compose exec api python scripts/import_chatbot_logs.py --reset

# LLM 필요 시 (선택 프로필)
docker compose --profile llm up -d ollama
docker exec finai-ollama ollama pull qwen2.5:7b
```

**B. 네이티브 실행 (로컬 개발)**

```bash
# DB만 도커, 앱은 호스트에서 hot reload
docker compose up -d postgres

alembic upgrade head
python scripts/import_compliance_mappings.py
python scripts/import_pii_risk.py
python scripts/import_isms_p.py

uvicorn main:app --reload --port 8000     # 터미널 1
streamlit run ui.py                       # 터미널 2
```

### 헬스체크

```
http://localhost:8000/health   → {"status":"ok"}
http://localhost:8000/docs     → Swagger UI
http://localhost:8501/         → Streamlit 대시보드
```

## 디렉토리 구조

```
finai-compliance/
├── api/              # FastAPI 라우터
│   ├── chat.py       # POST /chat 파이프라인 (개발자 A)
│   ├── logs.py       # GET /logs 진단 엔진 폴링용 (개발자 C)
│   └── health.py     # GET /health
├── core/
│   └── guardrails.py # PII 정규식 (개발자 A)
├── rag/
│   └── retrieve.py   # Chroma top-k 검색 (개발자 A)
├── llm/
│   ├── router.py     # mode 분기 (개발자 A)
│   ├── internal.py   # Ollama 호출
│   └── external.py   # Mock LLM egress (EV-001)
├── db/               # 개발자 C
│   ├── models.py     # SQLAlchemy chatbot_logs
│   ├── repository.py # Fail-Loud insert/query
│   └── session.py    # async session 풀
├── middlewares/      # 개발자 C
│   ├── request_id.py
│   ├── timing.py
│   └── logging.py    # structlog
├── alembic/          # 마이그레이션 (v1 보호)
├── scripts/          # 초기 데이터 적재 (개발자 A)
├── tests/
├── data/chroma/      # gitignored
├── main.py           # FastAPI 엔트리
├── ui.py             # Streamlit 엔트리 (개발자 A)
├── docker-compose.yml
└── requirements.txt
```

## 역할

| 영역 | 담당 |
|------|------|
| Streamlit UI · `POST /chat` 파이프라인 · 가드레일 · RAG · LLM 라우터 · 초기 적재 스크립트 | 개발자 A |
| 진단 엔진 워커 · `target_url` 도메인 검증 · `intentional_vuln_tag` 정확도 측정 · Mock LLM Server · AWS 인프라 | 개발자 B |
| FastAPI 미들웨어 · `GET /logs` · `db/*` · alembic · 진단 대시보드 · AWS 보조 | 개발자 C |

## 스키마

`chatbot_logs` v1 — alembic 보호. 변경은 PR 리뷰 필수.
설계 문서는 vault 의 `chatbot_logs 스키마 v1 (설계 초안)` 노트 참조.

## 라이선스

내부 학습 프로젝트.
