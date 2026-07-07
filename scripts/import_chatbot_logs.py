"""챗봇 실 로그 JSONL → chatbot_logs 적재.

원천:
  - `docs/references/chatbot_sample_logs.jsonl` (초기 샘플)
  - 개발자 A 챗봇(`msj1613/finance-compliance-chatbot`) 실 export:
    `<chatbot repo>/logs/chatbot.jsonl` or `logs/chatbot_export.jsonl`

필드 매핑 (A 챗봇 ChatbotLogOut → 우리 v5 chatbot_logs):
  jsonl              → chatbot_logs
  ─────────────────────────────────
  id                 → (스킵, 우리 BigInteger 자동 생성)
  conversation_id    → conversation_id
  request_id         → request_id
  created_at         → created_at
  event_type         → event_type
  client_ip          → client_ip           # v5 진단팀 요청
  user_id            → user_id             # v5
  tool_name          → tool_name           # v5
  mode               → mode
  target_url         → target_url
  target_provider    → target_provider
  user_prompt        → user_input
  rag_context        → rag_context
  llm_response       → bot_response
  latency_ms         → response_time_ms
  status             → status
  error_detail       → error_detail
  guardrail_triggered→ guardrail_triggered (str → [str], JSONB)
  intentional_vuln_tag→ intentional_vuln_tag
  pii_detected       → pii_detected
  pii_fields         → pii_fields
  security_signals   → security_signals
  raw_request        → raw_request
  raw_response       → raw_response

Usage:
    python scripts/import_chatbot_logs.py                    # 실 로그 append
    python scripts/import_chatbot_logs.py --reset            # 기존 로그 전량 삭제 후 적재
    python scripts/import_chatbot_logs.py --path <파일경로>  # 다른 JSONL

브릿지 워크플로우 (개발자 A 챗봇 → 우리 DB):
    # A 챗봇 리포에서
    PYTHONPATH=. uv run python scripts/export_logs.py logs/chatbot_export.jsonl

    # 우리 리포에서
    python scripts/import_chatbot_logs.py --path <A레포>/logs/chatbot_export.jsonl --reset
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.models import ChatbotLog, DiagnosisResult
from db.session import SessionLocal


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSONL = REPO_ROOT / "docs" / "references" / "chatbot_sample_logs.jsonl"


def _guardrail(raw: Any) -> list:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return raw
    return [str(raw)]


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _uuid(raw: str | None) -> uuid.UUID | None:
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError):
        return None


def row_from_jsonl(rec: dict) -> dict:
    rid = _uuid(rec.get("request_id")) or uuid.uuid4()
    return {
        "request_id": rid,
        "conversation_id": _uuid(rec.get("conversation_id")),
        "created_at": _parse_ts(rec.get("created_at")),
        "event_type": rec.get("event_type") or "chat",
        "mode": rec.get("mode") or "internal",
        "user_input": rec.get("user_prompt") or "",
        "bot_response": rec.get("llm_response"),
        "rag_context": rec.get("rag_context"),
        "model_name": rec.get("target_provider"),  # 실 로그에 model_name 없음
        "response_time_ms": rec.get("latency_ms"),
        "target_url": rec.get("target_url"),
        "target_provider": rec.get("target_provider"),
        "status": rec.get("status") or "success",
        "error_detail": rec.get("error_detail"),
        "error_code": None,
        # v5 진단팀 요청 필드
        "client_ip": rec.get("client_ip"),
        "user_id": rec.get("user_id"),
        "tool_name": rec.get("tool_name"),
        "intentional_vuln_tag": rec.get("intentional_vuln_tag"),
        "guardrail_triggered": _guardrail(rec.get("guardrail_triggered")),
        "pii_detected": bool(rec.get("pii_detected")) if rec.get("pii_detected") is not None else False,
        "pii_fields": rec.get("pii_fields"),
        "security_signals": rec.get("security_signals"),
        "flagged": bool(rec.get("intentional_vuln_tag") or rec.get("guardrail_triggered")),
        "raw_request": rec.get("raw_request"),
        "raw_response": rec.get("raw_response"),
    }


async def load(path: Path, reset: bool) -> None:
    if not path.exists():
        raise FileNotFoundError(f"JSONL 없음: {path}")

    print(f"[읽기] {path}")
    records: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  L{i} 파싱 실패: {e}")

    print(f"  총 {len(records)}건 파싱")

    rows = [row_from_jsonl(r) for r in records]

    async with SessionLocal() as session:
        if reset:
            # diagnosis_results가 chatbot_logs를 FK로 참조 → 먼저 삭제
            await session.execute(delete(DiagnosisResult))
            await session.execute(delete(ChatbotLog))
            await session.flush()
            print("  [reset] 기존 chatbot_logs / diagnosis_results 전량 삭제")

        session.add_all([ChatbotLog(**r) for r in rows])
        await session.commit()

    print(f"[완료] {len(rows)}건 적재")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", type=Path, default=DEFAULT_JSONL, help="JSONL 파일 경로")
    ap.add_argument("--reset", action="store_true", help="기존 로그 전량 삭제 후 재적재")
    args = ap.parse_args()
    asyncio.run(load(args.path, args.reset))


if __name__ == "__main__":
    main()
