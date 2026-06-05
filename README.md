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

```bash
# 1. Python 가상환경
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # macOS/Linux

# 2. 의존성
pip install -r requirements-dev.txt

# 3. 환경 변수
copy .env.example .env    # Windows
# cp .env.example .env       # macOS/Linux
# .env 편집 (DB·Ollama·API 키)

# 4. Postgres + Ollama 컨테이너 기동
docker compose up -d

# 5. Ollama 모델 pull (최초 1회)
docker exec finai-ollama ollama pull EEVE-Korean-10.8B-v1.0

# 6. DB 마이그레이션
alembic upgrade head

# 7. 초기 데이터 적재
python scripts/fetch_finlife.py
python scripts/fetch_ecos.py
python scripts/seed_chroma.py

# 8. FastAPI
uvicorn main:app --reload --port 8000

# 9. Streamlit (다른 터미널)
streamlit run ui.py
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
