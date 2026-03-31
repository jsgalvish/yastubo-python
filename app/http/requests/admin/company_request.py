"""
Schemas Pydantic para endpoints de Companies (admin).
Equivale a los Form Requests de PHP para CompanyController y CompanyCommissionUserController.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

_VALID_STATUSES = {"active", "inactive", "archived"}
_HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?$")


# ─────────────────────────── Company schemas ─────────────────────────────────


class CompanyOut(BaseModel):
    id: int
    name: str
    short_code: str | None = None
    phone: str | None = None
    email: str | None = None
    description: str | None = None
    status: str | None = None
    status_label: str | None = None
    users_ids: list[int] = []
    commission_beneficiary_user_id: int | None = None
    branding_logo_file_id: int | None = None
    pdf_template_id: int | None = None
    branding: dict = {}

    model_config = {"from_attributes": True}


class UserBriefOut(BaseModel):
    id: int
    email: str
    display_name: str

    model_config = {"from_attributes": True}


class PdfTemplateOut(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class CompanyDetailOut(BaseModel):
    """Respuesta detallada del endpoint show (incluye relaciones y listas de apoyo)."""

    data: CompanyOut
    assigned_users: list[UserBriefOut] = []
    beneficiary_users: list[UserBriefOut] = []
    branding_defaults: dict = {}
    pdf_templates: list[PdfTemplateOut] = []


class StoreCompanyRequest(BaseModel):
    name: str = Field(..., max_length=255)
    short_code: str = Field(..., min_length=3, max_length=5, pattern=r"^[A-Za-z]+$")


class UpdateCompanyRequest(BaseModel):
    name: str | None = Field(None, max_length=255)
    short_code: str | None = Field(None, min_length=3, max_length=5, pattern=r"^[A-Za-z]+$")
    phone: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=255)
    description: str | None = None
    status: str | None = None
    users: list[int] | None = None
    commission_beneficiary_user_id: int | None = None
    branding_text_dark: str | None = Field(None, max_length=7)
    branding_bg_light: str | None = Field(None, max_length=7)
    branding_text_light: str | None = Field(None, max_length=7)
    branding_bg_dark: str | None = Field(None, max_length=7)
    branding_logo_remove: bool | None = None
    pdf_template_id: int | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_STATUSES:
            raise ValueError(f"Estado inválido. Valores permitidos: {sorted(_VALID_STATUSES)}")
        return v

    @field_validator(
        "branding_text_dark",
        "branding_bg_light",
        "branding_text_light",
        "branding_bg_dark",
        mode="before",
    )
    @classmethod
    def validate_hex_color(cls, v: str | None) -> str | None:
        if v is not None and not _HEX_RE.match(v):
            raise ValueError("El color debe ser un valor hexadecimal válido (ej: #FFFFFF o FFFFFF).")
        return v


# ─────────────────────────── Pagination ──────────────────────────────────────


class PaginationMeta(BaseModel):
    current_page: int
    last_page: int
    per_page: int
    total: int


class UserSearchItemOut(BaseModel):
    id: int
    email: str
    display_name: str
    is_attached: bool


class PaginatedUsersOut(BaseModel):
    data: list[UserSearchItemOut]
    meta: PaginationMeta


# ─────────────────────────── Short code check ────────────────────────────────


class ShortCodeCheckOut(BaseModel):
    short_code: str
    is_available: bool
    reason: str | None = None


# ─────────────────────────── Commission User schemas ─────────────────────────


class CommissionUserBriefOut(BaseModel):
    id: int
    email: str
    display_name: str

    model_config = {"from_attributes": True}


class CommissionUserOut(BaseModel):
    id: int
    user_id: int
    commission: str  # formateado con 2 decimales
    user: CommissionUserBriefOut | None = None


class StoreCommissionUserRequest(BaseModel):
    user_id: int


class UpdateCommissionRequest(BaseModel):
    commission: float = Field(..., ge=0, le=100)


class AvailableUserItemOut(BaseModel):
    id: int
    email: str
    display_name: str
    attached: bool
    commission_user_id: int | None = None


class PaginatedAvailableUsersOut(BaseModel):
    data: list[AvailableUserItemOut]
    meta: PaginationMeta
