"""
Schemas Pydantic para endpoints de Capitados Core (admin).
Equivale a CapitatedPersonController.php + CapitatedContractController.php.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


# ─────────────────────────── Person ──────────────────────────────────────────


class PersonOut(BaseModel):
    id: int
    company_id: int
    product_id: int
    document_number: str
    full_name: str
    sex: str
    age_reported: Optional[int] = None
    status: Optional[str] = None
    residence_country_id: Optional[int] = None
    repatriation_country_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PaginationMeta(BaseModel):
    current_page: int
    last_page: int
    per_page: int
    total: int


class PersonIndexResponse(BaseModel):
    data: list[PersonOut]
    meta: PaginationMeta


# ─────────────────────────── Contract ────────────────────────────────────────


class ContractOut(BaseModel):
    id: int
    company_id: int
    product_id: int
    person_id: int
    status: str
    entry_date: Optional[str] = None
    valid_until: Optional[str] = None
    entry_age: Optional[int] = None
    uuid: Optional[str] = None
    wtime_suicide_ends_at: Optional[str] = None
    wtime_preexisting_conditions_ends_at: Optional[str] = None
    wtime_accident_ends_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ContractIndexResponse(BaseModel):
    data: list[ContractOut]
    meta: PaginationMeta


class PersonDetailResponse(BaseModel):
    person: PersonOut
    contracts: list[ContractOut]


class MonthlyRecordOut(BaseModel):
    id: int
    coverage_month: Optional[str] = None
    full_name: str
    sex: str
    age_reported: Optional[int] = None
    residence_country_id: Optional[int] = None
    repatriation_country_id: Optional[int] = None
    price_base: Optional[float] = None
    price_final: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ContractDetailResponse(BaseModel):
    contract: ContractOut
    last_monthly_record: Optional[MonthlyRecordOut] = None


# ─────────────────────────── Capitados index ─────────────────────────────────


class CompanyOut(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class ProductOut(BaseModel):
    id: int
    company_id: Optional[int] = None
    status: Optional[str] = None
    product_type: str
    show_in_widget: bool
    name: Optional[str] = None
    description: Optional[str] = None
    active_plan_version_id: Optional[int] = None
    has_active_plan_version: bool

    model_config = ConfigDict(from_attributes=True)


class CapitatedProductsResponse(BaseModel):
    company: CompanyOut
    products: list[ProductOut]
