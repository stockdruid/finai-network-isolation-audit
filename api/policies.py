"""정책 매핑 조회 API."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from db.session import get_session

router = APIRouter()


@router.get("/policies")
async def list_policies(
    category: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await repo.list_policies(session, category=category)
    return [row.to_dict() for row in rows]
