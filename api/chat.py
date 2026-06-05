"""POST /chat 파이프라인 — 개발자 A 구현.

흐름:
    request → core.guardrails (PII 정규식)
            → rag.retrieve (top-k)
            → llm.router (mode 분기)
                ├── mode=internal → llm.internal (Ollama)
                └── mode=external → llm.external (Mock LLM, EV-001 시나리오)
            → db.repository.insert_log (Fail-Loud, 실패 시 503)
"""
from fastapi import APIRouter

router = APIRouter()


# TODO(개발자 A): POST /chat 엔드포인트 구현
