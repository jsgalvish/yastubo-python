from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

# ── Requests ──────────────────────────────────────────────────────────────────


class CreateUserRequest(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    display_name: str | None = Field(None, max_length=150)
    email: EmailStr
    status: Literal["active", "suspended", "locked"] = "active"
    roles: list[str] = []
    # Staff profile (opcional)
    work_phone: str | None = Field(None, max_length=50)
    commission_regular_first_year_pct: float | None = Field(None, ge=0, le=100)
    commission_regular_renewal_pct: float | None = Field(None, ge=0, le=100)
    commission_capitados_pct: float | None = Field(None, ge=0, le=100)

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.strip().lower()


class UpdateUserRequest(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    display_name: str | None = Field(None, max_length=150)
    email: EmailStr
    status: Literal["active", "suspended", "locked"] = "active"
    roles: list[str] | None = None
    # Staff profile
    work_phone: str | None = Field(None, max_length=50)
    notes_admin: str | None = Field(None, max_length=10000)
    commission_regular_first_year_pct: float | None = Field(None, ge=0, le=100)
    commission_regular_renewal_pct: float | None = Field(None, ge=0, le=100)
    commission_capitados_pct: float | None = Field(None, ge=0, le=100)

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.strip().lower()


class UpdateStatusRequest(BaseModel):
    status: Literal["active", "suspended", "locked"]


# ── Responses ─────────────────────────────────────────────────────────────────


class StaffProfileOut(BaseModel):
    work_phone: str | None = None
    notes_admin: str | None = None
    commission_regular_first_year_pct: float | None = None
    commission_regular_renewal_pct: float | None = None
    commission_capitados_pct: float | None = None

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: int
    realm: str
    email: str
    first_name: str
    last_name: str | None = None
    display_name: str | None = None
    status: str
    force_password_change: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    last_login_at: datetime | None = None
    roles: list[str] = []

    model_config = {"from_attributes": True}


class UserDetailOut(UserOut):
    staff_profile: StaffProfileOut | None = None


class PaginatedUsersOut(BaseModel):
    data: list[UserOut]
    meta: dict[str, Any]


class SearchUserItem(BaseModel):
    id: int
    display_name: str
    email: str
    status: str


class SearchUsersOut(BaseModel):
    data: list[SearchUserItem]
    meta: dict[str, Any]
