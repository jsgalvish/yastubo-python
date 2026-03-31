"""
Controlador de capitados core (admin).
Equivale a CapitatedPersonController.php + CapitatedContractController.php.

Endpoints:
  GET /admin/companies/{cid}/capitados/persons              → personsIndex
  GET /admin/companies/{cid}/capitados/persons/{pid}         → personsShow
  GET /admin/companies/{cid}/capitados/contracts             → contractsIndex
  GET /admin/companies/{cid}/capitados/contracts/{ctid}      → contractsShow

Permiso: admin.companies.manage (acceso a empresa)
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.http.middleware.permission import require_permission
from app.http.requests.admin.capitated_request import (
    CapitatedProductsResponse,
    CompanyOut,
    ContractDetailResponse,
    ContractIndexResponse,
    ContractOut,
    MonthlyRecordOut,
    PaginationMeta,
    PersonDetailResponse,
    PersonIndexResponse,
    PersonOut,
    ProductOut,
)
from app.models.capitated_contract import CapitatedContract
from app.models.capitated_monthly_record import CapitatedMonthlyRecord
from app.models.capitated_product_insured import CapitatedProductInsured
from app.models.company import Company
from app.models.plan_version import PlanVersion
from app.models.product import Product
from app.models.user import User

router = APIRouter(
    prefix="/admin/companies/{company_id}/capitados",
    tags=["admin:capitated"],
)

_PERMISSION = "admin.companies.manage"


# ─────────────────────────── Helpers ─────────────────────────────────────────


async def _get_company(company_id: int, db: AsyncSession) -> Company:
    r = await db.execute(select(Company).where(Company.id == company_id))
    c = r.scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    return c


def _person_out(p: CapitatedProductInsured) -> PersonOut:
    return PersonOut(
        id=p.id,
        company_id=p.company_id,
        product_id=p.product_id,
        document_number=p.document_number,
        full_name=p.full_name,
        sex=p.sex,
        age_reported=p.age_reported,
        status=p.status,
        residence_country_id=p.residence_country_id,
        repatriation_country_id=p.repatriation_country_id,
    )


def _contract_out(c: CapitatedContract) -> ContractOut:
    return ContractOut(
        id=c.id,
        company_id=c.company_id,
        product_id=c.product_id,
        person_id=c.person_id,
        status=c.status,
        entry_date=str(c.entry_date) if c.entry_date else None,
        valid_until=str(c.valid_until) if c.valid_until else None,
        entry_age=c.entry_age,
        uuid=c.uuid,
        wtime_suicide_ends_at=str(c.wtime_suicide_ends_at) if c.wtime_suicide_ends_at else None,
        wtime_preexisting_conditions_ends_at=str(c.wtime_preexisting_conditions_ends_at)
        if c.wtime_preexisting_conditions_ends_at
        else None,
        wtime_accident_ends_at=str(c.wtime_accident_ends_at) if c.wtime_accident_ends_at else None,
    )


def _monthly_record_out(mr: CapitatedMonthlyRecord) -> MonthlyRecordOut:
    return MonthlyRecordOut(
        id=mr.id,
        coverage_month=str(mr.coverage_month) if mr.coverage_month else None,
        full_name=mr.full_name,
        sex=mr.sex,
        age_reported=mr.age_reported,
        residence_country_id=mr.residence_country_id,
        repatriation_country_id=mr.repatriation_country_id,
        price_base=float(mr.price_base) if mr.price_base is not None else None,
        price_final=float(mr.price_final) if mr.price_final is not None else None,
    )


def _pagination_meta(total: int, page: int, per_page: int) -> PaginationMeta:
    return PaginationMeta(
        current_page=page,
        last_page=max(1, math.ceil(total / per_page)),
        per_page=per_page,
        total=total,
    )


# ─────────────────────────── Capitados (products) ────────────────────────────


@router.get("", response_model=CapitatedProductsResponse)
async def capitados_index(
    company_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> CapitatedProductsResponse:
    """Planes capitados de una empresa con su versión activa."""
    company = await _get_company(company_id, db)

    products_r = await db.execute(
        select(Product)
        .where(
            Product.company_id == company_id,
            Product.product_type == Product.TYPE_PLAN_CAPITADO,
        )
        .order_by(Product.id)
    )
    products = list(products_r.scalars().all())

    active_versions: dict[int, int] = {}
    if products:
        product_ids = [p.id for p in products]
        av_r = await db.execute(
            select(PlanVersion.product_id, PlanVersion.id).where(
                PlanVersion.product_id.in_(product_ids),
                PlanVersion.status == PlanVersion.STATUS_ACTIVE,
            )
        )
        for pid, vid in av_r.all():
            active_versions[pid] = vid

    return CapitatedProductsResponse(
        company=CompanyOut(id=company.id, name=company.name),
        products=[
            ProductOut(
                id=p.id,
                company_id=p.company_id,
                status=p.status,
                product_type=p.product_type,
                show_in_widget=p.show_in_widget,
                name=p.name,
                description=p.description,
                active_plan_version_id=active_versions.get(p.id),
                has_active_plan_version=p.id in active_versions,
            )
            for p in products
        ],
    )


# ─────────────────────────── Persons ─────────────────────────────────────────


@router.get("/persons", response_model=PersonIndexResponse)
async def persons_index(
    company_id: int,
    product_id: int | None = Query(default=None),
    per_page: int = Query(default=15, ge=1, le=100),
    page: int = Query(default=1, ge=1),
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> PersonIndexResponse:
    """Lista paginada de asegurados de una empresa."""
    await _get_company(company_id, db)

    base_q = select(CapitatedProductInsured).where(CapitatedProductInsured.company_id == company_id)
    if product_id is not None:
        base_q = base_q.where(CapitatedProductInsured.product_id == product_id)

    base_q = base_q.order_by(CapitatedProductInsured.full_name)

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    items = list(
        (await db.execute(base_q.offset((page - 1) * per_page).limit(per_page))).scalars().all()
    )

    return PersonIndexResponse(
        data=[_person_out(p) for p in items],
        meta=_pagination_meta(total, page, per_page),
    )


@router.get("/persons/{person_id}", response_model=PersonDetailResponse)
async def persons_show(
    company_id: int,
    person_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> PersonDetailResponse:
    """Detalle de un asegurado con sus contratos."""
    await _get_company(company_id, db)

    r = await db.execute(
        select(CapitatedProductInsured).where(
            CapitatedProductInsured.id == person_id,
            CapitatedProductInsured.company_id == company_id,
        )
    )
    person = r.scalar_one_or_none()
    if person is None:
        raise HTTPException(status_code=404, detail="Asegurado no encontrado.")

    contracts_r = await db.execute(
        select(CapitatedContract)
        .where(CapitatedContract.person_id == person_id)
        .order_by(CapitatedContract.id.desc())
    )

    return PersonDetailResponse(
        person=_person_out(person),
        contracts=[_contract_out(c) for c in contracts_r.scalars().all()],
    )


# ─────────────────────────── Contracts ───────────────────────────────────────


@router.get("/contracts", response_model=ContractIndexResponse)
async def contracts_index(
    company_id: int,
    status: str = Query(default="active"),
    product_id: int | None = Query(default=None),
    q: str = Query(default=""),
    per_page: int = Query(default=15, ge=1, le=100),
    page: int = Query(default=1, ge=1),
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> ContractIndexResponse:
    """Lista paginada de contratos de una empresa con búsqueda."""
    await _get_company(company_id, db)

    base_q = (
        select(CapitatedContract)
        .join(CapitatedProductInsured, CapitatedContract.person_id == CapitatedProductInsured.id)
        .where(CapitatedContract.company_id == company_id)
    )

    if status != "all":
        base_q = base_q.where(CapitatedContract.status == status)

    if product_id is not None:
        base_q = base_q.where(CapitatedContract.product_id == product_id)

    search = q.strip()
    if search:
        like = f"%{search}%"
        filters = [
            CapitatedProductInsured.full_name.ilike(like),
            CapitatedProductInsured.document_number.ilike(like),
        ]
        if search.isdigit():
            filters.append(CapitatedContract.id == int(search))  # type: ignore[arg-type]
        base_q = base_q.where(or_(*filters))

    base_q = base_q.order_by(CapitatedContract.id.desc())

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    items = list(
        (await db.execute(base_q.offset((page - 1) * per_page).limit(per_page))).scalars().all()
    )

    return ContractIndexResponse(
        data=[_contract_out(c) for c in items],
        meta=_pagination_meta(total, page, per_page),
    )


@router.get("/contracts/{contract_id}", response_model=ContractDetailResponse)
async def contracts_show(
    company_id: int,
    contract_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> ContractDetailResponse:
    """Detalle de un contrato con último registro mensual."""
    await _get_company(company_id, db)

    r = await db.execute(
        select(CapitatedContract).where(
            CapitatedContract.id == contract_id,
            CapitatedContract.company_id == company_id,
        )
    )
    contract = r.scalar_one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Contrato no encontrado.")

    # Último registro mensual
    mr_r = await db.execute(
        select(CapitatedMonthlyRecord)
        .where(CapitatedMonthlyRecord.contract_id == contract_id)
        .order_by(CapitatedMonthlyRecord.coverage_month.desc())
        .limit(1)
    )
    last_mr = mr_r.scalar_one_or_none()

    return ContractDetailResponse(
        contract=_contract_out(contract),
        last_monthly_record=_monthly_record_out(last_mr) if last_mr else None,
    )
