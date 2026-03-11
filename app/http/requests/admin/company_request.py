"""
Schemas Pydantic para endpoints de Companies y CompanyCommissionUsers (admin).
Equivale a los Form Requests de PHP para CompanyController y CompanyCommissionUserController.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, field_validator


# ─────────────────────────── Branding ────────────────────────────────────────

class BrandingOut(BaseModel):
    text_dark: Optional[str] = None
    bg_light: Optional[str] = None
    text_light: Optional[str] = None
    bg_dark: Optional[str] = None
    logo: dict = {}


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
    name: str
    short_code: str


class UpdateCompanyRequest(BaseModel):
    name: Optional[str] = None
    short_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    users: Optional[list[int]] = None
    commission_beneficiary_user_id: Optional[int] = None
    branding_text_dark: Optional[str] = None
    branding_bg_light: Optional[str] = None
    branding_text_light: Optional[str] = None
    branding_bg_dark: Optional[str] = None
    branding_logo_remove: Optional[bool] = None
    pdf_template_id: Optional[int] = None


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
    commission: float


class AvailableUserItemOut(BaseModel):
    id: int
    email: str
    display_name: str
    attached: bool
    commission_user_id: Optional[int] = None


class PaginatedAvailableUsersOut(BaseModel):
    data: list[AvailableUserItemOut]
    meta: PaginationMeta


# ─────────────────────────── Short code check ────────────────────────────────

class ShortCodeCheckOut(BaseModel):
    short_code: str
    is_available: bool
    reason: Optional[str] = None
