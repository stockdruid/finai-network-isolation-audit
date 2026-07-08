import httpx

from core.config import settings


async def call_external_mock(prompt: str, context: str | None = None) -> str:
    """외부 LLM mock 서버 호출.

    이 호출 자체가 EV-001 망분리 위반 시나리오. 실제 HTTP egress가 발생해야
    진단 엔진이 탐지할 수 있다.
    """
    user_content = prompt
    if context:
        # 컨텍스트도 외부로 같이 나가는 위험 시나리오 (EV-002 잠재 시드)
        user_content = f"참고 자료:\n{context}\n\n질문: {prompt}"

    payload = {
        "model": "gpt-4-mock",
        "messages": [{"role": "user", "content": user_content}],
    }
    headers = {"Authorization": f"Bearer {settings.external_llm_api_key}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(settings.external_llm_url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()

    return data["choices"][0]["message"]["content"]
