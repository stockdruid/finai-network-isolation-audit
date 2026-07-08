"""엔드포인트 공용 헬퍼 - 클라이언트 IP / 유저 식별.

진단 엔진 요청(2026-07-07): DDoS 방어·행위 추적을 위해 IP와 user_id를 로그에 남긴다.
"""

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from db.chatbot_repo import get_user_by_token


def get_client_ip(request: Request) -> str:
    """요청 클라이언트 IP. (프록시 뒤라면 X-Forwarded-For 우선)"""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def resolve_user_id(request: Request, session: AsyncSession) -> str | None:
    """세션 토큰(Authorization: Bearer / X-Session-Token)으로 유저 식별. 없으면 None."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    else:
        token = request.headers.get("x-session-token")
    if not token:
        return None
    user = await get_user_by_token(session, token)
    return user.id if user else None
