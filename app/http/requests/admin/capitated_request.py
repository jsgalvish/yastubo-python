"""
Schemas Pydantic para endpoints de Capitados Core (admin).
Equivale a CapitatedPersonController.php + CapitatedContractController.php.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# ─────────────────────────── Person ──────────────────────────────────────────


class PersonOut(BaseModel):
    id: int
    company_id: int
    product_id: int
    document_number: str
    full_name: str
    sex: str
    age_reported: int | None = None
    status: str | None = None
    residence_country_id: int | None = None
    repatriation_country_id: int | None = None

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
    entry_date: str | None = None
    valid_until: str | None = None
    entry_age: int | None = None
    uuid: str | None = None
    wtime_suicide_ends_at: str | None = None
    wtime_preexisting_conditions_ends_at: str | None = None
    wtime_accident_ends_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ContractIndexResponse(BaseModel):
    data: list[ContractOut]
    meta: PaginationMeta


class PersonDetailResponse(BaseModel):
    person: PersonOut
    contracts: list[ContractOut]


class MonthlyRecordOut(BaseModel):
    id: int
    coverage_month: str | None = None
    full_name: str
    sex: str
    age_reported: int | None = None
    residence_country_id: int | None = None
    repatriation_country_id: int | None = None
    price_base: float | None = None
    price_final: float | None = None

    model_config = ConfigDict(from_attributes=True)


class ContractDetailResponse(BaseModel):
    contract: ContractOut
    last_monthly_record: MonthlyRecordOut | None = None


# ─────────────────────────── Capitados index ─────────────────────────────────


class CompanyOut(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class ProductOut(BaseModel):
    id: int
    company_id: int | None = None
    status: str | None = None
    product_type: str
    show_in_widget: bool
    name: str | None = None
    description: str | None = None
    active_plan_version_id: int | None = None
    has_active_plan_version: bool

    model_config = ConfigDict(from_attributes=True)


class CapitatedProductsResponse(BaseModel):
    company: CompanyOut
    products: list[ProductOut]
