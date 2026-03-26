from __future__ import annotations

from pydantic import BaseModel, EmailStr, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.strip().lower()


class UserInfo(BaseModel):
    id: int
    name: str
    email: str
    roles: list[str] = []
    permissions: list[str] = []


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    force_password_change: bool = False
    user: UserInfo | None = None
