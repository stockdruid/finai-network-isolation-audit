from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_client_ip, resolve_user_id
from core.logging import get_logger
from db.models import ChatbotLog, User
from db.chatbot_repo import get_user_by_id, insert_log, list_all_users
from db.session import get_session
from schemas.user import UserAdminOut

log = get_logger(__name__)
router = APIRouter()


async def _log_access(
    session: AsyncSession,
    *,
    event_type: str,
    target: str,
    signals: dict,
    exposed: dict | None,
    client_ip: str,
    user_id: str | None,
) -> None:
    """민감 데이터 접근을 로그로 남긴다 (진단 엔진이 위반을 탐지하도록)."""
    entry = ChatbotLog(
        conversation_id=str(uuid4()),
        request_id=str(uuid4()),
        event_type=event_type,
        client_ip=client_ip,
        user_id=user_id,
        tool_name=event_type,
        mode="internal",
        target_url=target,
        target_provider="api",
        user_prompt=f"{event_type}: {target}",
        status="success",
        pii_detected=True,
        pii_fields=["username", "password", "ssn", "phone", "email"],
        security_signals=signals,
        raw_response=exposed,  # 노출된 민감 데이터가 로그에 그대로 남음
    )
    await insert_log(session, entry)


@router.get("/admin/users", response_model=list[UserAdminOut])
async def admin_list_users(
    request: Request, session: AsyncSession = Depends(get_session)
):
    # INTENTIONAL VULN: 인증/인가 전혀 없음 (Broken Access Control).
    # 누구나 전 사용자의 평문 비밀번호/주민번호를 덤프할 수 있다.
    users = await list_all_users(session)
    await _log_access(
        session,
        event_type="admin_access",
        target="/admin/users",
        signals={
            "broken_access_control": True,
            "no_auth_admin": True,
            "bulk_pii_dump": True,
        },
        exposed={"user_count": len(users), "usernames": [u.username for u in users]},
        client_ip=get_client_ip(request),
        user_id=await resolve_user_id(request, session),
    )
    log.warning("admin_users_dumped", count=len(users))
    return users


@router.get("/users/{user_id}", response_model=UserAdminOut)
async def get_user(
    user_id: str, request: Request, session: AsyncSession = Depends(get_session)
):
    # INTENTIONAL VULN: 객체 소유권 검증 없음 (IDOR / BOLA).
    # ID만 알면 누구나 남의 계정 정보를 조회할 수 있다.
    user = await get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    await _log_access(
        session,
        event_type="user_lookup",
        target=f"/users/{user_id}",
        signals={"idor": True, "object_authz_missing": True},
        exposed={"username": user.username},
        client_ip=get_client_ip(request),
        user_id=await resolve_user_id(request, session),
    )
    log.warning("user_idor_access", user_id=user_id)
    return user
