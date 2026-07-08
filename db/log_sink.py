"""JSONL 파일 sink.

설계 §1.2 Dual Sink Logging: DB(단일 진실원) + JSON 파일(진단 엔진 전달용).
모든 로그를 DB에 넣은 뒤, 같은 내용을 logs/chatbot.jsonl에 한 줄씩 append 한다.
파일 포맷은 GET /logs 응답과 동일하도록 ChatbotLogOut을 재사용한다.
"""

import json
from pathlib import Path

from core.config import settings
from core.logging import get_logger
from db.models import ChatbotLog
from schemas.log import ChatbotLogOut

log = get_logger(__name__)


def append_jsonl(entry: ChatbotLog) -> None:
    """로그 1건을 JSONL 파일에 append. 보조 sink라 실패해도 챗봇을 막지 않는다.

    (단일 진실원은 DB이므로, 파일이 깨져도 scripts/export_logs.py로 재생성 가능)
    """
    try:
        path = Path(settings.log_file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = ChatbotLogOut.model_validate(entry).model_dump(mode="json")
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        log.error("jsonl_sink_failed", request_id=entry.request_id, error=str(e))
