from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)
    # 아래 PII는 선택 입력. 넣으면 평문으로 저장됨 (의도적 취약점).
    ssn: str | None = None  # 주민등록번호
    phone: str | None = None
    email: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    user_id: str
    username: str
    session_token: str
