"""
Schemas Pydantic para endpoints de Capitados Lotes y Reportes Mensuales (admin).
Equivale a CapitatedBatchController.php + CapitatedMonthlyReportController.php.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# ─────────────────────────── Batch ───────────────────────────────────────────


class BatchOut(BaseModel):
    id: int
    company_id: int
    coverage_month: str | None = None
    status: str
    source: str
    original_filename: str | None = None
    total_rows: int = 0
    total_applied: int = 0
    total_rejected: int = 0
    total_duplicated: int = 0
    total_incongruences: int = 0
    total_plan_errors: int = 0
    total_rolled_back: int = 0
    created_by_user_id: int | None = None
    processed_at: str | None = None

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
    sheet_name: str | None = None
    row_number: int | None = None
    product_id: int | None = None
    document_number: str | None = None
    full_name: str | None = None
    sex: str | None = None
    age_reported: int | None = None
    result: str | None = None
    rejection_code: str | None = None
    rejection_detail: str | None = None
    residence_raw: str | None = None
    repatriation_raw: str | None = None

    model_config = ConfigDict(from_attributes=True)


class BatchItemsResponse(BaseModel):
    data: list[BatchItemOut]
    meta: PaginationMeta


# ─────────────────────────── Monthly Records ─────────────────────────────────


class MonthlyRecordBatchOut(BaseModel):
    id: int
    person_id: int
    contract_id: int
    coverage_month: str | None = None
    full_name: str
    sex: str
    age_reported: int | None = None
    price_base: float | None = None
    price_final: float | None = None
    status: str | None = None

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
    active_total: float | None = None


class MonthlyReportMonthsResponse(BaseModel):
    months: list[MonthSummaryOut]
