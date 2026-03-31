"""
Schemas Pydantic para endpoints de Dashboard & Config (admin).
Equivale a DashboardController.php + ConfigController.php.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────────── Dashboard ───────────────────────────────────────


class CompanyCard(BaseModel):
    id: int
    name: str
    short_code: str | None = None
    status: str
    logo_file_id: int | None = None


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


class RetailStats(BaseModel):
    total_subscriptions: int
    active: int
    mrr_cents: int


class DashboardResponse(BaseModel):
    beneficiarios: BeneficiarioStats
    mrr_capitado: float
    mrr_retail_cents: int
    retail: RetailStats
    companies: list[CompanyCard]
    recent_batches: list[BatchCard]


# ─────────────────────────── ConfigItem ──────────────────────────────────────


class ConfigItemOut(BaseModel):
    id: int
    category: str | None = None
    token: str
    name: str | None = None
    type: str
    config: str | None = None
    value_int: int | None = None
    value_decimal: float | None = None
    value_text: str | None = None
    value_trans: str | None = None
    value_date: str | None = None
    value_file_plain_id: int | None = None
    value_file_es_id: int | None = None
    value_file_en_id: int | None = None

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
    config: dict | None = None


class UpdateDefinitionRequest(BaseModel):
    category: str | None = None
    name: str | None = Field(None, max_length=255)
    token: str | None = Field(None, max_length=191)
    type: str | None = Field(None, max_length=100)
    config: dict | None = None


class UpdateValueRequest(BaseModel):
    value: Any = None


# ─────────────────────────── SystemSetting ───────────────────────────────────


class SystemSettingOut(BaseModel):
    id: int
    category: str | None = None
    key: str
    value_json: str | None = None

    model_config = ConfigDict(from_attributes=True)
