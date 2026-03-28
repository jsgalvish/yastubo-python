"""
Schemas Pydantic para endpoints de Capitados Lotes y Reportes Mensuales (admin).
Equivale a CapitatedBatchController.php + CapitatedMonthlyReportController.php.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


# ─────────────────────────── Batch ───────────────────────────────────────────


class BatchOut(BaseModel):
    id: int
    company_id: int
    coverage_month: Optional[str] = None
    status: str
    source: str
    original_filename: Optional[str] = None
    total_rows: int = 0
    total_applied: int = 0
    total_rejected: int = 0
    total_duplicated: int = 0
    total_incongruences: int = 0
    total_plan_errors: int = 0
    total_rolled_back: int = 0
    created_by_user_id: Optional[int] = None
    processed_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginationMeta(BaseModel):
    current_page: int
    last_page: int
    per_page: int
    total: int


class BatchIndexResponse(BaseModel):
    data: list[BatchOut]
    meta: PaginationMeta


class BatchDetailResponse(BaseModel):
    data: BatchOut


# ─────────────────────────── Batch Items ─────────────────────────────────────


class BatchItemOut(BaseModel):
    id: int
    batch_id: int
    sheet_name: Optional[str] = None
    row_number: Optional[int] = None
    product_id: Optional[int] = None
    document_number: Optional[str] = None
    full_name: Optional[str] = None
    sex: Optional[str] = None
    age_reported: Optional[int] = None
    result: Optional[str] = None
    rejection_code: Optional[str] = None
    rejection_detail: Optional[str] = None
    residence_raw: Optional[str] = None
    repatriation_raw: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BatchItemsResponse(BaseModel):
    data: list[BatchItemOut]
    meta: PaginationMeta


# ─────────────────────────── Monthly Records ─────────────────────────────────


class MonthlyRecordBatchOut(BaseModel):
    id: int
    person_id: int
    contract_id: int
    coverage_month: Optional[str] = None
    full_name: str
    sex: str
    age_reported: Optional[int] = None
    price_base: Optional[float] = None
    price_final: Optional[float] = None
    status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MonthlyRecordsBatchResponse(BaseModel):
    data: list[MonthlyRecordBatchOut]
    meta: PaginationMeta


# ─────────────────────────── Rollback ────────────────────────────────────────


class RollbackResponse(BaseModel):
    message: str


# ─────────────────────────── Monthly Report ──────────────────────────────────


class MonthSummaryOut(BaseModel):
    month: str
    active_count: int
    active_total: Optional[float] = None


class MonthlyReportMonthsResponse(BaseModel):
    months: list[MonthSummaryOut]
