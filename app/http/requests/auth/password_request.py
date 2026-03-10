from __future__ import annotations

from pydantic import BaseModel, EmailStr, field_validator


class PasswordCheckRequest(BaseModel):
    password: str
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    email: str | None = None


class PasswordCheckResponse(BaseModel):
    valid: bool
    errors: list[str]


class ChangePasswordRequest(BaseModel):
    current_password: str
    password: str
    password_confirmation: str

    @field_validator("password_confirmation")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Las contraseñas no coinciden.")
        return v


class ForcePasswordRequest(BaseModel):
    current_password: str
    password: str
    password_confirmation: str

    @field_validator("password_confirmation")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Las contraseñas no coinciden.")
        return v
