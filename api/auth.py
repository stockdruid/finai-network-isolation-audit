from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_client_ip
from core.logging import get_logger
from db.models import ChatbotLog, User
from db.chatbot_repo import create_user, get_user_by_username, insert_log
from db.session import get_session
from schemas.auth import AuthResponse, LoginRequest, SignupRequest

log = get_logger(__name__)
router = APIRouter(prefix="/auth")


def _weak_token(username: str) -> str:
    # INTENTIONAL VULN: 예측 가능한 약한 세션 토큰 (랜덤성 없음)
    return f"sess-{username}"


async def _log_auth_event(
    session: AsyncSession,
    *,
    event_type: str,
    username: str,
    password: str,
    pii_fields: list[str],
    client_ip: str,
    user_id: str | None = None,
    status: str = "success",
) -> None:
    """인증 이벤트를 chatbot_logs에 기록.

    INTENTIONAL VULN: raw_request에 평문 비밀번호가 그대로 남아 진단 엔진이
    보는 로그(JSONL/API)에 인증정보가 노출된다. (auth_info_in_log)
    """
    entry = ChatbotLog(
        conversation_id=str(uuid4()),
        request_id=str(uuid4()),
        event_type=event_type,
        client_ip=client_ip,
        user_id=user_id,
        tool_name="auth",
        mode="internal",
        target_url="local://auth/" + event_type,
        target_provider="auth",
        user_prompt=f"{event_type}: {username}",
        status=status,
        pii_detected=bool(pii_fields),
        pii_fields=pii_fields or None,
        security_signals={
            "password_storage": "plaintext",
            "auth_info_in_log": True,
            "weak_session_token": True,
        },
        # 평문 자격증명이 로그에 그대로 노출됨
        raw_request={"username": username, "password": password},
    )
    await insert_log(session, entry)


@router.post("/signup", response_model=AuthResponse)
async def signup(
    req: SignupRequest, request: Request, session: AsyncSession = Depends(get_session)
):
    existing = await get_user_by_username(session, req.username)
    if existing is not None:
        raise HTTPException(status_code=409, detail="username already exists")

    # INTENTIONAL VULN: 비밀번호/PII 평문 저장
    user = User(
        username=req.username,
        password=req.password,
        ssn=req.ssn,
        phone=req.phone,
        email=req.email,
        session_token=_weak_token(req.username),
    )
    await create_user(session, user)

    pii_fields = [f for f in ("ssn", "phone", "email") if getattr(req, f)]
    await _log_auth_event(
        session,
        event_type="signup",
        username=req.username,
        password=req.password,
        pii_fields=pii_fields,
        client_ip=get_client_ip(request),
        user_id=user.id,
    )
    log.info("signup", username=req.username, pii_fields=pii_fields)

    return AuthResponse(
        user_id=user.id, username=user.username, session_token=user.session_token
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    req: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)
):
    client_ip = get_client_ip(request)
    user = await get_user_by_username(session, req.username)
    # INTENTIONAL VULN: 평문 비밀번호 직접 비교 (해시 검증 없음)
    if user is None or user.password != req.password:
        await _log_auth_event(
            session,
            event_type="login",
            username=req.username,
            password=req.password,
            pii_fields=[],
            client_ip=client_ip,
            status="error",
        )
        raise HTTPException(status_code=401, detail="invalid credentials")

    await _log_auth_event(
        session,
        event_type="login",
        username=req.username,
        password=req.password,
        pii_fields=[],
        client_ip=client_ip,
        user_id=user.id,
    )
    log.info("login", username=req.username)

    return AuthResponse(
        user_id=user.id, username=user.username, session_token=user.session_token
    )
