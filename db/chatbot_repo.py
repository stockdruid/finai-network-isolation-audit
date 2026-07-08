from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.log_sink import append_jsonl
from db.models import ChatbotLog, User


class LogPersistenceError(Exception):
    """로그 적재 실패. main.py에서 잡아서 503으로 변환."""


async def insert_log(session: AsyncSession, log: ChatbotLog) -> ChatbotLog:
    try:
        session.add(log)
        await session.commit()
        await session.refresh(log)
    except Exception as e:
        await session.rollback()
        raise LogPersistenceError(str(e)) from e
    # DB 적재 성공 후 파일 sink (보조) - 진단 엔진 전달용 JSONL
    append_jsonl(log)
    return log


async def list_logs(
    session: AsyncSession,
    *,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    mode: str | None = None,
    conversation_id: str | None = None,
    target_url_contains: str | None = None,
    limit: int = 100,
):
    # 진단 엔진(개발자 B)이 폴링할 때 쓰는 함수
    stmt = select(ChatbotLog).order_by(ChatbotLog.created_at.desc())

    if from_dt:
        stmt = stmt.where(ChatbotLog.created_at >= from_dt)
    if to_dt:
        stmt = stmt.where(ChatbotLog.created_at <= to_dt)
    if mode:
        stmt = stmt.where(ChatbotLog.mode == mode)
    if conversation_id:
        stmt = stmt.where(ChatbotLog.conversation_id == conversation_id)
    if target_url_contains:
        stmt = stmt.where(ChatbotLog.target_url.contains(target_url_contains))

    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_conversation_history(
    session: AsyncSession, conversation_id: str, limit: int = 6
) -> list[ChatbotLog]:
    """대화 메모리용 - 같은 conversation_id의 성공한 chat 로그를 오래된 순으로 반환.

    후속 질문("그 중에 뭐가 제일 싸?")의 맥락을 LLM에 넘겨주기 위함.
    최근 limit건만 (컨텍스트 폭주 방지).
    """
    stmt = (
        select(ChatbotLog)
        .where(
            ChatbotLog.conversation_id == conversation_id,
            ChatbotLog.event_type == "chat",
            ChatbotLog.status == "success",
            ChatbotLog.llm_response.is_not(None),
        )
        .order_by(ChatbotLog.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    return list(reversed(rows))  # 오래된 순으로


async def get_log_by_id(session: AsyncSession, log_id: str) -> ChatbotLog | None:
    stmt = select(ChatbotLog).where(ChatbotLog.id == log_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# --- User (로그인) ---


async def create_user(session: AsyncSession, user: User) -> User:
    # INTENTIONAL VULN: password/ssn을 평문 그대로 저장 (해싱/암호화 없음)
    try:
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    except Exception as e:
        await session.rollback()
        raise LogPersistenceError(str(e)) from e


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_token(session: AsyncSession, token: str) -> User | None:
    stmt = select(User).where(User.session_token == token)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_all_users(session: AsyncSession) -> list[User]:
    # INTENTIONAL VULN: 인가 검증 없이 전체 사용자 반환 (관리자 API에서 사용)
    stmt = select(User).order_by(User.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_recent_requests(
    session: AsyncSession, conversation_id: str, seconds: int = 60
) -> int:
    """최근 N초 내 같은 대화의 요청 수. 무제한 자원소비(LLM10) 탐지용."""
    since = datetime.utcnow() - timedelta(seconds=seconds)
    stmt = (
        select(func.count())
        .select_from(ChatbotLog)
        .where(
            ChatbotLog.conversation_id == conversation_id,
            ChatbotLog.created_at >= since,
        )
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())
