import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_client_ip, resolve_user_id
from core.guardrails import (
    check_strict,
    detect_injection,
    find_url,
    redact_pii,
    response_leaked_secret,
)
from core.logging import get_logger
from db.models import ChatbotLog
from db.chatbot_repo import (
    LogPersistenceError,
    count_recent_requests,
    insert_log,
    list_conversation_history,
)
from db.session import get_session
from llm.router import call_llm
from rag.retrieve import retrieve
from schemas.chat import ChatRequest, ChatResponse

log = get_logger(__name__)
router = APIRouter()

TOP_K = 5


async def _save_log(session: AsyncSession, log_entry: ChatbotLog, request_id: str):
    try:
        await insert_log(session, log_entry)
    except LogPersistenceError as e:
        log.error("log_persistence_failed", request_id=request_id, error=str(e))
        raise HTTPException(status_code=503, detail="Log persistence failed") from e


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest, request: Request, session: AsyncSession = Depends(get_session)
):
    request_id = str(uuid4())
    conversation_id = req.conversation_id or str(uuid4())

    # 진단 엔진 요청: IP·유저 식별 (DDoS 방어·행위 추적용)
    client_ip = get_client_ip(request)
    user_id = await resolve_user_id(request, session)

    # 1) STRICT 가드레일 — 매칭 시 즉시 차단
    blocked_rule = check_strict(req.prompt)
    if blocked_rule:
        log_entry = ChatbotLog(
            conversation_id=conversation_id,
            request_id=request_id,
            client_ip=client_ip,
            user_id=user_id,
            tool_name="guardrail",
            mode=req.mode,
            target_url="",  # 차단되어 호출 안 함
            target_provider="blocked",
            user_prompt=redact_pii(req.prompt),  # PII 마스킹 후 저장
            status="blocked",
            guardrail_triggered=blocked_rule,
        )
        await _save_log(session, log_entry, request_id)
        log.warning("guardrail_blocked", request_id=request_id, rule=blocked_rule)
        raise HTTPException(
            status_code=403,
            detail={"code": "GUARDRAIL_BLOCKED", "rule": blocked_rule},
        )

    # 2) RAG 검색
    hits = retrieve(req.prompt, top_k=TOP_K)
    context_text = "\n\n".join(doc for doc, _ in hits) if hits else None

    # 의도적 취약점 태그 모음 (EV-002, EV-003)
    extra_vuln_tags: list[str] = []

    # EV-002: RAG에 고객 persona 포함 시 PII 노출 위험
    if any(meta.get("source") == "customer_persona" for _, meta in hits):
        extra_vuln_tags.append("EV-002")

    # EV-003: 프롬프트 인젝션 감지 (의도적으로 차단하지 않고 통과)
    if detect_injection(req.prompt):
        extra_vuln_tags.append("EV-003")

    # 보안 신호 모음 (EV 번호 대신 명시 신호로 진단 엔진에 전달)
    security_signals: dict = {}
    # 진단 엔진 요청: 유저 입력에 외부 주소가 들어오면 로그에 남김
    input_url = find_url(req.prompt)
    if input_url:
        security_signals["user_input_external_url"] = input_url

    # 무제한 자원소비(OWASP LLM10): rate limit·토큰 상한이 없음. 차단하지 않고 신호만.
    if len(req.prompt) > 1000:
        security_signals["resource_abuse"] = "oversized_prompt"
    recent_count = await count_recent_requests(session, conversation_id, seconds=60)
    if recent_count >= 10:
        security_signals["resource_abuse"] = "high_request_rate"

    # EV-002: 고객 persona가 컨텍스트에 포함되면 PII 노출 신호
    pii_detected = "EV-002" in extra_vuln_tags
    pii_fields = ["customer_name", "phone", "email"] if pii_detected else None

    # 이전 대화 불러오기 (후속 질문 맥락 유지) - 같은 conversation_id의 성공 로그
    prior = await list_conversation_history(session, conversation_id, limit=6)
    history: list[dict] = []
    for p in prior:
        history.append({"role": "user", "content": p.user_prompt})
        history.append({"role": "assistant", "content": p.llm_response})

    # 3) LLM 호출
    started = time.perf_counter()
    try:
        result = await call_llm(req.mode, req.prompt, context=context_text, history=history)
    except Exception as e:
        latency_ms = int((time.perf_counter() - started) * 1000)
        log.error("llm_call_failed", request_id=request_id, mode=req.mode, error=str(e))
        # INTENTIONAL VULN: 원본 에러 detail을 로그에 그대로 남김 (진단 엔진이 탐지)
        err_entry = ChatbotLog(
            conversation_id=conversation_id,
            request_id=request_id,
            client_ip=client_ip,
            user_id=user_id,
            tool_name="llm_error",
            mode=req.mode,
            target_url="",
            target_provider="error",
            user_prompt=req.prompt,
            rag_context=context_text,
            latency_ms=latency_ms,
            status="error",
            error_detail=repr(e),
            intentional_vuln_tag=",".join(extra_vuln_tags) or None,
            pii_detected=pii_detected,
            pii_fields=pii_fields,
            security_signals={**security_signals, "error_detail_leaked": True},
        )
        try:
            await _save_log(session, err_entry, request_id)
        except HTTPException:
            pass  # 로그 실패해도 원래 502를 우선 전달
        raise HTTPException(status_code=502, detail="upstream LLM error") from e
    latency_ms = int((time.perf_counter() - started) * 1000)

    # EV-003 성공 판정: 응답에 시스템 프롬프트 내부 비밀이 새어나왔으면 신호로 기록
    if response_leaked_secret(result.response):
        security_signals["system_prompt_leaked"] = True
        if "EV-003" not in extra_vuln_tags:
            extra_vuln_tags.append("EV-003")

    # vuln_tag 합치기 (router의 EV-001 + 위에서 발견한 EV-002/003)
    all_vuln_tags = result.vuln_tags + extra_vuln_tags
    vuln_tag_str = ",".join(all_vuln_tags) if all_vuln_tags else None

    # 4) 로그 적재
    tool_name = "external_llm" if req.mode == "external" else "ollama_chat"
    log_entry = ChatbotLog(
        conversation_id=conversation_id,
        request_id=request_id,
        client_ip=client_ip,
        user_id=user_id,
        tool_name=tool_name,
        mode=req.mode,
        target_url=result.target_url,
        target_provider=result.target_provider,
        user_prompt=req.prompt,
        rag_context=context_text,
        llm_response=result.response,
        latency_ms=latency_ms,
        intentional_vuln_tag=vuln_tag_str,
        pii_detected=pii_detected,
        pii_fields=pii_fields,
        security_signals=security_signals or None,
    )
    await _save_log(session, log_entry, request_id)

    log.info(
        "chat_ok",
        request_id=request_id,
        mode=req.mode,
        provider=result.target_provider,
        vuln_tags=all_vuln_tags,
        latency_ms=latency_ms,
    )

    return ChatResponse(
        request_id=request_id,
        conversation_id=conversation_id,
        response=result.response,
        mode=req.mode,
        target_url=result.target_url,
        latency_ms=latency_ms,
    )
