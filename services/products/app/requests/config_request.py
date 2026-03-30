"""
Schemas Pydantic para endpoints de Dashboard & Config (admin).
Equivale a DashboardController.php + ConfigController.php.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────── Dashboard ───────────────────────────────────────


class CompanyCard(BaseModel):
    id: int
    name: str
    short_code: Optional[str] = None
    status: str
    logo_file_id: Optional[int] = None


class BatchCard(BaseModel):
    id: int
    company_id: int
    company_name: str
    coverage_month: str
    status: str
    total_rows: int
    total_applied: int
    total_rejected: int


class BeneficiarioStats(BaseModel):
    active: int
    rolled_back: int
    other: int
    total: int


class DashboardResponse(BaseModel):
    beneficiarios: BeneficiarioStats
    mrr_estimate: float
    companies: list[CompanyCard]
    recent_batches: list[BatchCard]


# ─────────────────────────── ConfigItem ──────────────────────────────────────


class ConfigItemOut(BaseModel):
    id: int
    category: Optional[str] = None
    token: str
    name: Optional[str] = None
    type: str
    config: Optional[str] = None
    value_int: Optional[int] = None
    value_decimal: Optional[float] = None
    value_text: Optional[str] = None
    value_trans: Optional[str] = None
    value_date: Optional[str] = None
    value_file_plain_id: Optional[int] = None
    value_file_es_id: Optional[int] = None
    value_file_en_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ConfigIndexResponse(BaseModel):
    items: list[ConfigItemOut]
    permissions: dict


class ConfigItemDataResponse(BaseModel):
    item: ConfigItemOut


class ConfigItemMessageResponse(BaseModel):
    item: ConfigItemOut
    message: str


# ─────────────────────────── Requests ────────────────────────────────────────


class StoreConfigItemRequest(BaseModel):
    category: str
    name: str = Field(..., max_length=255)
    token: str = Field(..., max_length=191)
    type: str = Field(..., max_length=100)
    config: Optional[dict] = None


class UpdateDefinitionRequest(BaseModel):
    category: Optional[str] = None
    name: Optional[str] = Field(None, max_length=255)
    token: Optional[str] = Field(None, max_length=191)
    type: Optional[str] = Field(None, max_length=100)
    config: Optional[dict] = None


class UpdateValueRequest(BaseModel):
    value: Any = None


# ─────────────────────────── SystemSetting ───────────────────────────────────


class SystemSettingOut(BaseModel):
    id: int
    category: Optional[str] = None
    key: str
    value_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
