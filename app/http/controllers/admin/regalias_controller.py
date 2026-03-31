"""
Controlador de regalías (admin).
Equivale a RegaliasController.php en Laravel.

Endpoints:
  GET    /admin/regalias/api/beneficiaries                                      → beneficiariesIndex
  GET    /admin/regalias/api/beneficiaries/{id}/origins/users/available          → availableOriginsUsers
  GET    /admin/regalias/api/beneficiaries/{id}/origins/units/available          → availableOriginsUnits
  POST   /admin/regalias/api/regalias                                           → store
  PATCH  /admin/regalias/api/regalias/{id}                                      → update
  DELETE /admin/regalias/api/regalias/{id}                                      → destroy

Permisos: regalia.users.read / regalia.users.edit
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.http.middleware.permission import require_permission
from app.http.requests.admin.regalia_request import (
    AvailableOriginUnitItem,
    AvailableOriginUserItem,
    BeneficiariesIndexResponse,
    BeneficiaryBriefOut,
    BeneficiaryGroupOut,
    OriginUnitOut,
    OriginUserOut,
    PaginatedAvailableUnitsResponse,
    PaginatedAvailableUsersResponse,
    PaginationMeta,
    RegaliaDataResponse,
    RegaliaDetailOut,
    RegaliaOut,
    StoreRegaliaRequest,
    UpdateRegaliaRequest,
)
from app.models.business_unit import BusinessUnit
from app.models.regalia import Regalia
from app.models.user import User
from app.services.regalias import RegaliasService

router = APIRouter(prefix="/admin/regalias/api", tags=["admin:regalias"])

_READ_PERM = "regalia.users.read"
_EDIT_PERM = "regalia.users.edit"


# ─────────────────────────── Helpers ─────────────────────────────────────────


def _regalia_out(r: Regalia) -> RegaliaOut:
    return RegaliaOut(
        id=r.id,
        beneficiary_user_id=r.beneficiary_user_id,
        source_type=r.source_type,
        source_id=r.source_id,
        commission=float(r.commission) if r.commission is not None else None,
    )


async def _get_regalia(regalia_id: int, db: AsyncSession) -> Regalia:
    result = await db.execute(
        select(Regalia).options(selectinload(Regalia.beneficiary)).where(Regalia.id == regalia_id)
    )
    reg = result.scalar_one_or_none()
    if reg is None:
        raise HTTPException(status_code=404, detail="Regalía no encontrada.")
    return reg


def _pagination_meta(total: int, page: int, per_page: int) -> PaginationMeta:
    return PaginationMeta(
        current_page=page,
        last_page=max(1, math.ceil(total / per_page)),
        per_page=per_page,
        total=total,
    )


# ─────────────────────────── beneficiariesIndex ──────────────────────────────


@router.get("/beneficiaries", response_model=BeneficiariesIndexResponse)
async def beneficiaries_index(
    per_page: int = Query(default=20, ge=1, le=100),
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    _current_user: User = Depends(require_permission(_READ_PERM)),
    db: AsyncSession = Depends(get_db),
) -> BeneficiariesIndexResponse:
    """Lista beneficiarios con sus regalías agrupadas."""
    # Subquery: user_ids que son beneficiarios
    ben_subq = select(Regalia.beneficiary_user_id).distinct().subquery()

    base_q = select(User).where(User.id.in_(select(ben_subq.c.beneficiary_user_id)))

    search = q.strip()
    if search:
        like = f"%{search}%"
        base_q = base_q.where(
            User.email.ilike(like) | User.first_name.ilike(like) | User.last_name.ilike(like)
        )

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0

    users = list(
        (
            await db.execute(
                base_q.order_by(User.first_name, User.last_name)
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        )
        .scalars()
        .all()
    )

    # Cargar regalías para estos beneficiarios
    user_ids = [u.id for u in users]
    regalias_r = (
        await db.execute(
            select(Regalia)
            .options(selectinload(Regalia.beneficiary))
            .where(Regalia.beneficiary_user_id.in_(user_ids))
            .order_by(Regalia.id)
        )
        if user_ids
        else None
    )
    all_regalias = list(regalias_r.scalars().all()) if regalias_r else []

    # Cargar origin users y units
    origin_user_ids = {r.source_id for r in all_regalias if r.source_type == "user"}
    origin_unit_ids = {r.source_id for r in all_regalias if r.source_type == "unit"}

    origin_users_map: dict[int, User] = {}
    if origin_user_ids:
        ou_r = await db.execute(select(User).where(User.id.in_(origin_user_ids)))
        origin_users_map = {u.id: u for u in ou_r.scalars().all()}

    origin_units_map: dict[int, BusinessUnit] = {}
    if origin_unit_ids:
        obu_r = await db.execute(select(BusinessUnit).where(BusinessUnit.id.in_(origin_unit_ids)))
        origin_units_map = {bu.id: bu for bu in obu_r.scalars().all()}

    # Agrupar por beneficiario
    groups = []
    for user in users:
        user_regalias = [r for r in all_regalias if r.beneficiary_user_id == user.id]
        detail_list = []
        for reg in user_regalias:
            origin_user = None
            origin_unit = None
            if reg.source_type == "user" and reg.source_id in origin_users_map:
                ou = origin_users_map[reg.source_id]
                origin_user = OriginUserOut(id=ou.id, display_name=ou.full_name, email=ou.email)
            elif reg.source_type == "unit" and reg.source_id in origin_units_map:
                obu = origin_units_map[reg.source_id]
                origin_unit = OriginUnitOut(id=obu.id, name=obu.name)

            detail_list.append(
                RegaliaDetailOut(
                    id=reg.id,
                    source_type=reg.source_type,
                    source_id=reg.source_id,
                    beneficiary_user_id=reg.beneficiary_user_id,
                    commission=float(reg.commission) if reg.commission is not None else None,
                    origin_user=origin_user,
                    origin_unit=origin_unit,
                )
            )

        groups.append(
            BeneficiaryGroupOut(
                beneficiary=BeneficiaryBriefOut(
                    id=user.id,
                    display_name=user.full_name,
                    email=user.email,
                    status=user.status,
                ),
                regalias=detail_list,
            )
        )

    return BeneficiariesIndexResponse(
        data=groups,
        meta={
            "pagination": _pagination_meta(total, page, per_page).model_dump(),
            "regalias_sources": RegaliasService(db).regalias_sources(),
        },
    )


# ─────────────────────────── availableOriginsUsers ───────────────────────────


@router.get(
    "/beneficiaries/{beneficiary_id}/origins/users/available",
    response_model=PaginatedAvailableUsersResponse,
)
async def available_origins_users(
    beneficiary_id: int,
    per_page: int = Query(default=20, ge=1, le=100),
    q: str = Query(default=""),
    status: str = Query(default="active"),
    page: int = Query(default=1, ge=1),
    _current_user: User = Depends(require_permission(_EDIT_PERM)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedAvailableUsersResponse:
    """Usuarios disponibles como origen de regalía para un beneficiario."""
    base_q = select(User).where(User.realm == "admin", User.deleted_at.is_(None))

    if status in ("active", "suspended", "locked"):
        base_q = base_q.where(User.status == status)

    search = q.strip()
    if search:
        like = f"%{search}%"
        base_q = base_q.where(
            User.email.ilike(like) | User.first_name.ilike(like) | User.last_name.ilike(like)
        )

    base_q = base_q.order_by(User.first_name, User.last_name)

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    users = list(
        (await db.execute(base_q.offset((page - 1) * per_page).limit(per_page))).scalars().all()
    )

    # IDs ya asignados
    assigned_r = await db.execute(
        select(Regalia.source_id).where(
            Regalia.beneficiary_user_id == beneficiary_id,
            Regalia.source_type == "user",
        )
    )
    assigned_ids = {row[0] for row in assigned_r.all()}

    data = [
        AvailableOriginUserItem(
            id=u.id,
            display_name=u.full_name,
            email=u.email,
            status=u.status,
            is_assigned=u.id in assigned_ids,
        )
        for u in users
    ]

    return PaginatedAvailableUsersResponse(
        data=data,
        meta=_pagination_meta(total, page, per_page),
    )


# ─────────────────────────── availableOriginsUnits ───────────────────────────


@router.get(
    "/beneficiaries/{beneficiary_id}/origins/units/available",
    response_model=PaginatedAvailableUnitsResponse,
)
async def available_origins_units(
    beneficiary_id: int,
    per_page: int = Query(default=20, ge=1, le=100),
    q: str = Query(default=""),
    status: str = Query(default="active"),
    page: int = Query(default=1, ge=1),
    _current_user: User = Depends(require_permission(_EDIT_PERM)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedAvailableUnitsResponse:
    """Business units disponibles como origen de regalía para un beneficiario."""
    base_q = select(BusinessUnit)

    if status in ("active", "inactive"):
        base_q = base_q.where(BusinessUnit.status == status)

    search = q.strip()
    if search:
        base_q = base_q.where(BusinessUnit.name.ilike(f"%{search}%"))

    base_q = base_q.order_by(BusinessUnit.name)

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    units = list(
        (await db.execute(base_q.offset((page - 1) * per_page).limit(per_page))).scalars().all()
    )

    # IDs ya asignados
    assigned_r = await db.execute(
        select(Regalia.source_id).where(
            Regalia.beneficiary_user_id == beneficiary_id,
            Regalia.source_type == "unit",
        )
    )
    assigned_ids = {row[0] for row in assigned_r.all()}

    data = [
        AvailableOriginUnitItem(
            id=bu.id,
            name=bu.name,
            status=bu.status,
            is_assigned=bu.id in assigned_ids,
        )
        for bu in units
    ]

    return PaginatedAvailableUnitsResponse(
        data=data,
        meta=_pagination_meta(total, page, per_page),
    )


# ─────────────────────────── store ───────────────────────────────────────────


@router.post("/regalias", response_model=RegaliaDataResponse, status_code=201)
async def store(
    body: StoreRegaliaRequest,
    _current_user: User = Depends(require_permission(_EDIT_PERM)),
    db: AsyncSession = Depends(get_db),
) -> RegaliaDataResponse:
    """Crea una regalia (delega validaciones al servicio)."""
    # Validar beneficiario
    ben_r = await db.execute(
        select(User).where(User.id == body.beneficiary_user_id, User.realm == "admin")
    )
    if ben_r.scalar_one_or_none() is None:
        raise HTTPException(status_code=422, detail="Beneficiario no valido.")

    service = RegaliasService(db)
    regalia = await service.create_regalia(
        beneficiary_id=body.beneficiary_user_id,
        source_type=body.source_type,
        source_id=body.source_id,
    )

    return RegaliaDataResponse(data=_regalia_out(regalia), message="Regalía creada.")


# ─────────────────────────── update ──────────────────────────────────────────


@router.patch("/regalias/{regalia_id}", response_model=RegaliaDataResponse)
async def update(
    regalia_id: int,
    body: UpdateRegaliaRequest,
    _current_user: User = Depends(require_permission(_EDIT_PERM)),
    db: AsyncSession = Depends(get_db),
) -> RegaliaDataResponse:
    """Actualiza la comision de una regalia."""
    regalia = await _get_regalia(regalia_id, db)

    service = RegaliasService(db)
    commission = body.commission if "commission" in body.model_fields_set else None
    regalia = await service.update_commission(regalia, commission)

    return RegaliaDataResponse(data=_regalia_out(regalia), message="Regalía actualizada.")


# ─────────────────────────── destroy ─────────────────────────────────────────


@router.delete("/regalias/{regalia_id}", response_model=RegaliaDataResponse)
async def destroy(
    regalia_id: int,
    _current_user: User = Depends(require_permission(_EDIT_PERM)),
    db: AsyncSession = Depends(get_db),
) -> RegaliaDataResponse:
    """Elimina una regalia."""
    regalia = await _get_regalia(regalia_id, db)
    out = _regalia_out(regalia)

    service = RegaliasService(db)
    await service.delete_regalia(regalia)

    return RegaliaDataResponse(data=out, message="Regalía eliminada.")
