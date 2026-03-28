"""
Schemas Pydantic para endpoints de Business Units (admin).
Equivale a BusinessUnitApiController.php.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

UnitType = Literal["consolidator", "office", "counter", "freelance"]
UnitStatus = Literal["active", "inactive"]


# ─────────────────────────── Unit output ─────────────────────────────────────


class UnitOut(BaseModel):
    id: int
    name: str
    type: Optional[str] = None
    status: Optional[str] = None
    parent_id: Optional[int] = None
    members_count: int = 0
    children_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class UnitDetailOut(UnitOut):
    branding_text_dark: Optional[str] = None
    branding_bg_light: Optional[str] = None
    branding_text_light: Optional[str] = None
    branding_bg_dark: Optional[str] = None
    branding_logo_file_id: Optional[int] = None


class UnitDataResponse(BaseModel):
    data: UnitOut


class UnitDetailResponse(BaseModel):
    data: UnitDetailOut


class PaginationMeta(BaseModel):
    current_page: int
    last_page: int
    per_page: int
    total: int


class UnitListResponse(BaseModel):
    data: list[UnitOut]
    meta: PaginationMeta


class ChildrenResponse(BaseModel):
    data: list[UnitOut]


# ─────────────────────────── Unit requests ───────────────────────────────────


class StoreUnitRequest(BaseModel):
    type: UnitType
    name: str = Field(..., max_length=255)
    parent_id: Optional[int] = None


class UpdateBasicRequest(BaseModel):
    name: str = Field(..., max_length=255)


class UpdateStatusRequest(BaseModel):
    status: UnitStatus


# ─────────────────────────── Members ─────────────────────────────────────────


class MemberOut(BaseModel):
    id: int
    business_unit_id: int
    user_id: int
    role_id: Optional[int] = None
    status: Optional[str] = None
    user_email: Optional[str] = None
    user_display_name: Optional[str] = None
    role_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MembersResponse(BaseModel):
    data: list[MemberOut]


class MemberDataResponse(BaseModel):
    data: MemberOut
    toast: dict


class LinkMemberRequest(BaseModel):
    user_id: int
    role_id: Optional[int] = None


class UpdateMemberRoleRequest(BaseModel):
    role_id: int


class UpdateMemberStatusRequest(BaseModel):
    status: UnitStatus


# ─────────────────────────── GSA Commissions ─────────────────────────────────


class GSACommissionOut(BaseModel):
    id: int
    source_type: str
    source_id: int
    beneficiary_user_id: int
    commission: Optional[float] = None
    user_email: Optional[str] = None
    user_display_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GSACommissionsResponse(BaseModel):
    data: list[GSACommissionOut]


class GSACommissionDataResponse(BaseModel):
    data: GSACommissionOut
    toast: dict


class AvailableGSAUserItem(BaseModel):
    id: int
    email: str
    display_name: str
    is_assigned: bool = False


class PaginatedAvailableGSAResponse(BaseModel):
    data: list[AvailableGSAUserItem]
    meta: PaginationMeta


class StoreGSACommissionRequest(BaseModel):
    user_id: int


class UpdateGSACommissionRequest(BaseModel):
    commission: Optional[float] = Field(None, ge=0, le=100)


# ─────────────────────────── Change Type / Move / Branding ────────────────────


class ChangeTypeRequest(BaseModel):
    target_type: UnitType
    detach_parent: bool = False


class MoveUnitRequest(BaseModel):
    parent_id: Optional[int] = None


class UpdateBrandingRequest(BaseModel):
    branding_text_dark: Optional[str] = Field(None, max_length=12)
    branding_bg_light: Optional[str] = Field(None, max_length=12)
    branding_text_light: Optional[str] = Field(None, max_length=12)
    branding_bg_dark: Optional[str] = Field(None, max_length=12)
    remove_logo: bool = False


# ─────────────────────────── Active users / Create user ──────────────────────


class ActiveUserOut(BaseModel):
    id: int
    email: str
    display_name: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class ActiveUsersResponse(BaseModel):
    data: list[ActiveUserOut]
    meta: PaginationMeta


class CreateUserMemberRequest(BaseModel):
    first_name: str = Field(..., max_length=255)
    last_name: str = Field(..., max_length=255)
    email: str = Field(..., max_length=255)
    role_id: int


class CreateUserMemberResponse(BaseModel):
    data: MemberOut
    toast: dict


# ─────────────────────────── Roles unit scope ────────────────────────────────


class RoleOut(BaseModel):
    id: int
    name: str
    scope: Optional[str] = None
    level: Optional[int] = None
    role_name: str

    model_config = ConfigDict(from_attributes=True)


class RolesResponse(BaseModel):
    data: list[RoleOut]
