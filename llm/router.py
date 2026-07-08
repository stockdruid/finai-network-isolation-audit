from dataclasses import dataclass, field

from core.config import settings
from llm.external import call_external_mock
from llm.internal import call_ollama


@dataclass
class LLMResult:
    response: str
    target_url: str
    target_provider: str
    # 의도적 취약점 태그 모음 (EV-001 등). 여러 개 가능.
    vuln_tags: list[str] = field(default_factory=list)


async def call_llm(
    mode: str,
    prompt: str,
    context: str | None = None,
    history: list[dict] | None = None,
) -> LLMResult:
    if mode == "external":
        text = await call_external_mock(prompt, context=context)
        return LLMResult(
            response=text,
            target_url=settings.external_llm_url,
            target_provider="openai_mock",
            vuln_tags=["EV-001"],  # 외부 LLM 호출 = 망분리 위반
        )

    text = await call_ollama(prompt, context=context, history=history)
    return LLMResult(
        response=text,
        target_url=f"{settings.ollama_base_url}/api/chat",
        target_provider="ollama",
        vuln_tags=[],
    )
