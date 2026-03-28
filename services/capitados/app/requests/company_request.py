"""
Schemas Pydantic para endpoints de Companies (admin).
Equivale a los Form Requests de PHP para CompanyController y CompanyCommissionUserController.
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_VALID_STATUSES = {"active", "inactive", "archived"}
_HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?$")


# ─────────────────────────── Company schemas ─────────────────────────────────


class CompanyOut(BaseModel):
    id: int
    name: str
    short_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    status_label: Optional[str] = None
    users_ids: list[int] = []
    commission_beneficiary_user_id: Optional[int] = None
    branding_logo_file_id: Optional[int] = None
    pdf_template_id: Optional[int] = None
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
    name: Optional[str] = Field(None, max_length=255)
    short_code: Optional[str] = Field(None, min_length=3, max_length=5, pattern=r"^[A-Za-z]+$")
    phone: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    users: Optional[list[int]] = None
    commission_beneficiary_user_id: Optional[int] = None
    branding_text_dark: Optional[str] = Field(None, max_length=7)
    branding_bg_light: Optional[str] = Field(None, max_length=7)
    branding_text_light: Optional[str] = Field(None, max_length=7)
    branding_bg_dark: Optional[str] = Field(None, max_length=7)
    branding_logo_remove: Optional[bool] = None
    pdf_template_id: Optional[int] = None

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
    reason: Optional[str] = None


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
    user: Optional[CommissionUserBriefOut] = None


class StoreCommissionUserRequest(BaseModel):
    user_id: int


class UpdateCommissionRequest(BaseModel):
    commission: float = Field(..., ge=0, le=100)


class AvailableUserItemOut(BaseModel):
    id: int
    email: str
    display_name: str
    attached: bool
    commission_user_id: Optional[int] = None


class PaginatedAvailableUsersOut(BaseModel):
    data: list[AvailableUserItemOut]
    meta: PaginationMeta
