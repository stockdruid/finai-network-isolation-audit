from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserAdminOut(BaseModel):
    """사용자 상세 - INTENTIONAL VULN.

    비밀번호/주민번호 등 민감 필드를 그대로 노출한다(Excessive Data Exposure).
    무인가 관리자 조회(/admin/users)와 IDOR(/users/{id})에서 이 스키마로 응답한다.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    password: str  # 평문 노출
    ssn: str | None
    phone: str | None
    email: str | None
    session_token: str | None
    created_at: datetime
