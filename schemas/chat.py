from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    mode: Literal["internal", "external"] = "internal"
    conversation_id: str | None = None  # 없으면 서버에서 새로 만듦


class ChatResponse(BaseModel):
    request_id: str
    conversation_id: str
    response: str
    mode: str
    target_url: str
    latency_ms: int
