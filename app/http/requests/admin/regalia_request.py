"""
Schemas Pydantic para endpoints de Regalías (admin).
Equivale a RegaliasController.php.

Skills aplicados:
  - Pydantic: Literal types, ConfigDict, response models tipados
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RegaliaSourceType = Literal["user", "unit"]


# ─────────────────────────── Output ──────────────────────────────────────────


class RegaliaOut(BaseModel):
    id: int
    beneficiary_user_id: int
    source_type: str
    source_id: int
    commission: float | None = None

    model_config = ConfigDict(from_attributes=True)


class RegaliaDataResponse(BaseModel):
    data: RegaliaOut
    message: str


class BeneficiaryBriefOut(BaseModel):
    id: int
    display_name: str
    email: str
    status: str | None = None


class OriginUserOut(BaseModel):
    id: int
    display_name: str
    email: str


class OriginUnitOut(BaseModel):
    id: int
    name: str


class RegaliaDetailOut(BaseModel):
    id: int
    source_type: str
    source_id: int
    beneficiary_user_id: int
    commission: float | None = None
    origin_user: OriginUserOut | None = None
    origin_unit: OriginUnitOut | None = None


class BeneficiaryGroupOut(BaseModel):
    beneficiary: BeneficiaryBriefOut
    regalias: list[RegaliaDetailOut]


class PaginationMeta(BaseModel):
    current_page: int
    last_page: int
    per_page: int
    total: int


class BeneficiariesIndexResponse(BaseModel):
    data: list[BeneficiaryGroupOut]
    meta: dict


class AvailableOriginUserItem(BaseModel):
    id: int
    display_name: str
    email: str
    status: str | None = None
    is_assigned: bool = False


class AvailableOriginUnitItem(BaseModel):
    id: int
    name: str
    status: str | None = None
    is_assigned: bool = False


class PaginatedAvailableUsersResponse(BaseModel):
    data: list[AvailableOriginUserItem]
    meta: PaginationMeta


class PaginatedAvailableUnitsResponse(BaseModel):
    data: list[AvailableOriginUnitItem]
    meta: PaginationMeta


# ─────────────────────────── Requests ────────────────────────────────────────


class StoreRegaliaRequest(BaseModel):
    beneficiary_user_id: int
    source_type: RegaliaSourceType
    source_id: int


class UpdateRegaliaRequest(BaseModel):
    commission: float | None = Field(None, ge=0, le=100)
