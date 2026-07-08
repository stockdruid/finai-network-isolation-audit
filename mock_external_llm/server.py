"""외부 LLM 시뮬레이션 서버.

실제 배포 환경에서는 VPC B (외부망)의 api.openai-mock.example.com 같은
별도 도메인으로 호스팅되어야 한다. 로컬 개발 시엔 localhost:9999.

진단 엔진(개발자 B)이 이 서버로의 호출 흔적을 chatbot_logs.target_url 로
탐지해서 망분리 위반(EV-001)으로 분류한다.

실행: PYTHONPATH=. uv run uvicorn mock_external_llm.server:app --port 9999
"""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock External LLM (api.openai-mock.example.com)")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest) -> dict[str, Any]:
    # OpenAI 응답 포맷 흉내
    user_msg = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    fake_reply = (
        "[외부 LLM mock 응답] "
        f"받은 질문: '{user_msg[:60]}...' — "
        "이 응답은 외부 LLM 시뮬레이션 서버에서 생성되었습니다. "
        "실제 배포 시 망분리 규제 위반에 해당합니다."
    )

    return {
        "id": "chatcmpl-mock-001",
        "object": "chat.completion",
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": fake_reply},
                "finish_reason": "stop",
            }
        ],
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-external-llm"}
