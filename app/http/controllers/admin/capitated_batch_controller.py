"""
Controlador de lotes capitados y reportes mensuales (admin).
Equivale a CapitatedBatchController.php + CapitatedMonthlyReportController.php.

Endpoints Batches:
  GET    /admin/companies/{cid}/capitados/batches                              → index
  GET    /admin/companies/{cid}/capitados/batches/{bid}                        → show
  GET    /admin/companies/{cid}/capitados/batches/{bid}/items                  → items
  GET    /admin/companies/{cid}/capitados/batches/{bid}/monthly-records        → monthlyRecords
  POST   /admin/companies/{cid}/capitados/batches/{bid}/rollback              → rollback
  POST   .../batches/{bid}/monthly-records/{rid}/rollback                      → rollbackMonthlyRecord

Endpoints Reports:
  GET    /admin/companies/{cid}/capitados/reportes/mensuales                   → months
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.http.middleware.permission import require_permission
from app.http.requests.admin.capitated_batch_request import (
    BatchDetailResponse,
    BatchIndexResponse,
    BatchItemOut,
    BatchItemsResponse,
    BatchOut,
    MonthlyRecordBatchOut,
    MonthlyRecordsBatchResponse,
    MonthlyReportMonthsResponse,
    MonthSummaryOut,
    PaginationMeta,
    RollbackResponse,
)
from app.models.capitated_batch_item_log import CapitatedBatchItemLog
from app.models.capitated_batch_log import CapitatedBatchLog
from app.models.capitated_monthly_record import CapitatedMonthlyRecord
from app.models.company import Company
from app.models.user import User

router = APIRouter(
    prefix="/admin/companies/{company_id}/capitados",
    tags=["admin:capitated-batches"],
)

_PERMISSION = "admin.companies.manage"


# ─────────────────────────── Helpers ─────────────────────────────────────────


async def _get_company(cid: int, db: AsyncSession) -> Company:
    r = await db.execute(select(Company).where(Company.id == cid))
    c = r.scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    return c


async def _get_batch(cid: int, bid: int, db: AsyncSession) -> CapitatedBatchLog:
    r = await db.execute(
        select(CapitatedBatchLog).where(
            CapitatedBatchLog.id == bid,
            CapitatedBatchLog.company_id == cid,
        )
    )
    b = r.scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")
    return b


def _batch_out(b: CapitatedBatchLog) -> BatchOut:
    return BatchOut(
        id=b.id,
        company_id=b.company_id,
        coverage_month=str(b.coverage_month) if b.coverage_month else None,
        status=b.status,
        source=b.source,
        original_filename=b.original_filename,
        total_rows=b.total_rows,
        total_applied=b.total_applied,
        total_rejected=b.total_rejected,
        total_duplicated=b.total_duplicated,
        total_incongruences=b.total_incongruences,
        total_plan_errors=b.total_plan_errors,
        total_rolled_back=b.total_rolled_back,
        created_by_user_id=b.created_by_user_id,
        processed_at=str(b.processed_at) if b.processed_at else None,
    )


def _item_out(i: CapitatedBatchItemLog) -> BatchItemOut:
    return BatchItemOut(
        id=i.id,
        batch_id=i.batch_id,
        sheet_name=i.sheet_name,
        row_number=i.row_number,
        product_id=i.product_id,
        document_number=i.document_number,
        full_name=i.full_name,
        sex=i.sex,
        age_reported=i.age_reported,
        result=i.result,
        rejection_code=i.rejection_code,
        rejection_detail=i.rejection_detail,
        residence_raw=i.residence_raw,
        repatriation_raw=i.repatriation_raw,
    )


def _mr_out(mr: CapitatedMonthlyRecord) -> MonthlyRecordBatchOut:
    return MonthlyRecordBatchOut(
        id=mr.id,
        person_id=mr.person_id,
        contract_id=mr.contract_id,
        coverage_month=str(mr.coverage_month) if mr.coverage_month else None,
        full_name=mr.full_name,
        sex=mr.sex,
        age_reported=mr.age_reported,
        price_base=float(mr.price_base) if mr.price_base is not None else None,
        price_final=float(mr.price_final) if mr.price_final is not None else None,
        status=mr.status,
    )


def _pagination_meta(total: int, page: int, per_page: int) -> PaginationMeta:
    return PaginationMeta(
        current_page=page,
        last_page=max(1, math.ceil(total / per_page)),
        per_page=per_page,
        total=total,
    )


# ─────────────────────────── Batches ─────────────────────────────────────────


@router.get("/batches", response_model=BatchIndexResponse)
async def batch_index(
    company_id: int,
    status: str = Query(default=""),
    per_page: int = Query(default=15, ge=1, le=100),
    page: int = Query(default=1, ge=1),
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> BatchIndexResponse:
    """Lista paginada de lotes de una empresa."""
    await _get_company(company_id, db)

    base_q = select(CapitatedBatchLog).where(CapitatedBatchLog.company_id == company_id)
    if status:
        base_q = base_q.where(CapitatedBatchLog.status == status)

    base_q = base_q.order_by(CapitatedBatchLog.id.desc())

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    items = list((await db.execute(
        base_q.offset((page - 1) * per_page).limit(per_page)
    )).scalars().all())

    return BatchIndexResponse(
        data=[_batch_out(b) for b in items],
        meta=_pagination_meta(total, page, per_page),
    )


@router.get("/batches/{batch_id}", response_model=BatchDetailResponse)
async def batch_show(
    company_id: int,
    batch_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> BatchDetailResponse:
    """Detalle de un lote."""
    batch = await _get_batch(company_id, batch_id, db)
    return BatchDetailResponse(data=_batch_out(batch))


@router.get("/batches/{batch_id}/items", response_model=BatchItemsResponse)
async def batch_items(
    company_id: int,
    batch_id: int,
    result: str = Query(default=""),
    sheet: str = Query(default=""),
    per_page: int = Query(default=25, ge=1, le=200),
    page: int = Query(default=1, ge=1),
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> BatchItemsResponse:
    """Lista paginada de ítems de un lote con filtros."""
    await _get_batch(company_id, batch_id, db)

    base_q = select(CapitatedBatchItemLog).where(CapitatedBatchItemLog.batch_id == batch_id)
    if result:
        base_q = base_q.where(CapitatedBatchItemLog.result == result)
    if sheet:
        base_q = base_q.where(CapitatedBatchItemLog.sheet_name == sheet)

    base_q = base_q.order_by(CapitatedBatchItemLog.row_number)

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    items = list((await db.execute(
        base_q.offset((page - 1) * per_page).limit(per_page)
    )).scalars().all())

    return BatchItemsResponse(
        data=[_item_out(i) for i in items],
        meta=_pagination_meta(total, page, per_page),
    )


@router.get("/batches/{batch_id}/monthly-records", response_model=MonthlyRecordsBatchResponse)
async def batch_monthly_records(
    company_id: int,
    batch_id: int,
    status: str = Query(default=""),
    product_id: int | None = Query(default=None),
    per_page: int = Query(default=25, ge=1, le=200),
    page: int = Query(default=1, ge=1),
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> MonthlyRecordsBatchResponse:
    """Lista monthly records generados por un lote."""
    await _get_batch(company_id, batch_id, db)

    base_q = select(CapitatedMonthlyRecord).where(CapitatedMonthlyRecord.load_batch_id == batch_id)
    if status:
        base_q = base_q.where(CapitatedMonthlyRecord.status == status)
    if product_id is not None:
        base_q = base_q.where(CapitatedMonthlyRecord.product_id == product_id)

    base_q = base_q.order_by(CapitatedMonthlyRecord.id)

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    items = list((await db.execute(
        base_q.offset((page - 1) * per_page).limit(per_page)
    )).scalars().all())

    return MonthlyRecordsBatchResponse(
        data=[_mr_out(mr) for mr in items],
        meta=_pagination_meta(total, page, per_page),
    )


# ─────────────────────────── Rollback ────────────────────────────────────────


@router.post("/batches/{batch_id}/rollback", response_model=RollbackResponse)
async def batch_rollback(
    company_id: int,
    batch_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> RollbackResponse:
    """Rollback completo de un lote (marca monthly records como rolled_back)."""
    batch = await _get_batch(company_id, batch_id, db)

    if batch.status != CapitatedBatchLog.STATUS_PROCESSED:
        raise HTTPException(status_code=422, detail="Solo se pueden revertir lotes procesados.")

    if batch.rolled_back_at is not None:
        raise HTTPException(status_code=422, detail="El lote ya fue revertido.")

    now = datetime.now(timezone.utc)

    # Marcar monthly records activos como rolled_back
    records_r = await db.execute(
        select(CapitatedMonthlyRecord).where(
            CapitatedMonthlyRecord.load_batch_id == batch_id,
            CapitatedMonthlyRecord.status == CapitatedMonthlyRecord.STATUS_ACTIVE,
        )
    )
    count = 0
    for mr in records_r.scalars().all():
        mr.status = CapitatedMonthlyRecord.STATUS_ROLLED_BACK
        mr.rolled_back_at = now
        mr.rolled_back_by_user_id = _current_user.id
        count += 1

    batch.status = CapitatedBatchLog.STATUS_ROLLED_BACK
    batch.rolled_back_at = now
    batch.rolled_back_by_user_id = _current_user.id
    batch.total_rolled_back = count

    await db.commit()

    return RollbackResponse(message=f"Lote revertido. {count} registros afectados.")


@router.post(
    "/batches/{batch_id}/monthly-records/{record_id}/rollback",
    response_model=RollbackResponse,
)
async def rollback_monthly_record(
    company_id: int,
    batch_id: int,
    record_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> RollbackResponse:
    """Rollback de un solo monthly record."""
    await _get_batch(company_id, batch_id, db)

    r = await db.execute(
        select(CapitatedMonthlyRecord).where(
            CapitatedMonthlyRecord.id == record_id,
            CapitatedMonthlyRecord.load_batch_id == batch_id,
        )
    )
    mr = r.scalar_one_or_none()
    if mr is None:
        raise HTTPException(status_code=404, detail="Registro mensual no encontrado.")

    if mr.status == CapitatedMonthlyRecord.STATUS_ROLLED_BACK:
        raise HTTPException(status_code=422, detail="El registro ya fue revertido.")

    mr.status = CapitatedMonthlyRecord.STATUS_ROLLED_BACK
    mr.rolled_back_at = datetime.now(timezone.utc)
    mr.rolled_back_by_user_id = _current_user.id

    await db.commit()

    return RollbackResponse(message="Registro mensual revertido correctamente.")


# ─────────────────────────── Monthly Reports ─────────────────────────────────


@router.get("/reportes/mensuales", response_model=MonthlyReportMonthsResponse)
async def report_months(
    company_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> MonthlyReportMonthsResponse:
    """Lista meses disponibles con conteos y totales."""
    await _get_company(company_id, db)

    r = await db.execute(
        select(
            CapitatedMonthlyRecord.coverage_month,
            func.count().filter(
                CapitatedMonthlyRecord.status == CapitatedMonthlyRecord.STATUS_ACTIVE
            ).label("active_count"),
            func.sum(CapitatedMonthlyRecord.price_final).filter(
                CapitatedMonthlyRecord.status == CapitatedMonthlyRecord.STATUS_ACTIVE
            ).label("active_total"),
        )
        .where(CapitatedMonthlyRecord.company_id == company_id)
        .group_by(CapitatedMonthlyRecord.coverage_month)
        .order_by(CapitatedMonthlyRecord.coverage_month.desc())
    )

    months = []
    for row in r.all():
        months.append(MonthSummaryOut(
            month=str(row[0]) if row[0] else "",
            active_count=row[1] or 0,
            active_total=float(row[2]) if row[2] is not None else None,
        ))

    return MonthlyReportMonthsResponse(months=months)
