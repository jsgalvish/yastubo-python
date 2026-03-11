"""
Controlador de empresas y usuarios de comisiones (admin).
Equivale a CompanyController.php + CompanyCommissionUserController.php en Laravel.

Endpoints de Company:
  GET    /admin/companies                              → index
  GET    /admin/companies/check-short-code             → checkShortCode
  POST   /admin/companies                              → store
  GET    /admin/companies/{id}                         → show
  PUT    /admin/companies/{id}                         → update
  PUT    /admin/companies/{id}/suspend                 → suspend
  PUT    /admin/companies/{id}/archive                 → archive
  PUT    /admin/companies/{id}/activate                → activate
  GET    /admin/companies/{id}/users/search            → searchUsers (paginado)
  POST   /admin/companies/{id}/users/{user_id}         → attachUser
  DELETE /admin/companies/{id}/users/{user_id}         → detachUser

Endpoints de CommissionUser:
  GET    /admin/companies/{id}/commission-users                      → index
  GET    /admin/companies/{id}/commission-users/available            → available
  POST   /admin/companies/{id}/commission-users                      → store
  PATCH  /admin/companies/{id}/commission-users/{ccu_id}             → update
  DELETE /admin/companies/{id}/commission-users/{ccu_id}             → destroy

Permiso requerido: admin.companies.manage
"""
from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.http.middleware.permission import require_permission
from app.http.requests.admin.company_request import (
    AvailableUserItemOut,
    CommissionUserOut,
    CompanyDetailOut,
    CompanyOut,
    PaginatedAvailableUsersOut,
    PaginatedUsersOut,
    PaginationMeta,
    PdfTemplateOut,
    ShortCodeCheckOut,
    StoreCommissionUserRequest,
    StoreCompanyRequest,
    UpdateCommissionRequest,
    UpdateCompanyRequest,
    UserBriefOut,
    UserSearchItemOut,
)
from app.models.company import Company
from app.models.company_commission_user import CompanyCommissionUser
from app.models.company_user import CompanyUser
from app.models.template import Template
from app.models.user import User

router = APIRouter(prefix="/admin/companies", tags=["admin:companies"])

_PERMISSION = "admin.companies.manage"
_VALID_STATUSES = {Company.STATUS_ACTIVE, Company.STATUS_INACTIVE, Company.STATUS_ARCHIVED}


# ─────────────────────────── Helpers ─────────────────────────────────────────

def _color_out(val: str | None) -> str | None:
    """Añade '#' al color si tiene valor (equivale a brandingConfig en PHP)."""
    if val:
        return f"#{val.lstrip('#')}"
    return None


def _branding_config(company: Company) -> dict:
    """Equivale a Company::brandingConfig() en PHP."""
    return {
        "text_dark": _color_out(company.branding_text_dark),
        "bg_light": _color_out(company.branding_bg_light),
        "text_light": _color_out(company.branding_text_light),
        "bg_dark": _color_out(company.branding_bg_dark),
        "logo": {
            "file_id": company.branding_logo_file_id,
            "is_custom": company.branding_logo_file_id is not None,
        },
    }


def _branding_defaults() -> dict:
    """Equivale a Company::brandingDefaults() en PHP (sin ConfigItem por ahora)."""
    return {
        "text_dark": None,
        "bg_light": None,
        "text_light": None,
        "bg_dark": None,
        "logo": {"file_id": None, "is_custom": False},
    }


def _build_company_out(company: Company) -> CompanyOut:
    """Equivale a transformCompany() en PHP."""
    return CompanyOut(
        id=company.id,
        name=company.name,
        short_code=company.short_code,
        phone=company.phone,
        email=company.email,
        description=company.description,
        status=company.status,
        status_label=company.status,
        users_ids=[cu.user_id for cu in company.users],
        commission_beneficiary_user_id=company.commission_beneficiary_user_id,
        branding_logo_file_id=company.branding_logo_file_id,
        pdf_template_id=company.pdf_template_id,
        branding=_branding_config(company),
    )


def _user_brief(user: User) -> UserBriefOut:
    return UserBriefOut(
        id=user.id,
        email=user.email,
        display_name=user.full_name,
    )


async def _get_company(company_id: int, db: AsyncSession) -> Company:
    """
    Carga una empresa con sus relaciones básicas. 404 si no existe.
    Expira el mapa de identidad para garantizar datos frescos después de mutaciones
    (necesario con expire_on_commit=False).
    """
    db.expire_all()
    result = await db.execute(
        select(Company)
        .options(selectinload(Company.users))
        .where(Company.id == company_id)
    )
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    return company


# ─────────────────────────── Company: index / check-short-code ───────────────

@router.get("/check-short-code", response_model=ShortCodeCheckOut)
async def check_short_code(
    short_code: str = Query(default=""),
    company_id: Optional[int] = Query(default=None),
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """
    Verifica si un short_code está disponible.
    Equivale a checkShortCode() en PHP.
    """
    sc = short_code.strip().upper()

    if sc == "":
        return ShortCodeCheckOut(short_code=sc, is_available=False, reason="empty")

    q = select(Company).where(func.upper(Company.short_code) == sc)
    if company_id:
        q = q.where(Company.id != company_id)

    existing = (await db.execute(q)).scalar_one_or_none()
    is_available = existing is None

    return ShortCodeCheckOut(
        short_code=sc,
        is_available=is_available,
        reason=None if is_available else "taken",
    )


@router.get("", response_model=dict)
async def index(
    status: str = Query(default="active"),
    search: str = Query(default=""),
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista de empresas con filtros opcionales de status y búsqueda.
    Equivale a index() JSON branch en PHP.
    """
    q = select(Company).options(selectinload(Company.users))

    if status != "all" and status in _VALID_STATUSES:
        q = q.where(Company.status == status)

    search = search.strip()
    if search:
        like = f"%{search}%"
        q = q.where(
            Company.name.ilike(like)
            | Company.short_code.ilike(like)
            | Company.phone.ilike(like)
            | Company.email.ilike(like)
        )

    q = q.order_by(Company.name)
    companies = list((await db.execute(q)).scalars().all())

    return {
        "companies": [_build_company_out(c) for c in companies],
        "filters": {"status": status, "search": search},
    }


# ─────────────────────────── Company: store / show / update ──────────────────

@router.post("", response_model=dict, status_code=201)
async def store(
    body: StoreCompanyRequest,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Crea una nueva empresa. Equivale a store() en PHP."""
    sc = body.short_code.strip().upper()

    existing = (await db.execute(
        select(Company).where(func.upper(Company.short_code) == sc)
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=422, detail="El short_code ya existe.")

    company = Company()
    company.name = body.name.strip()
    company.short_code = sc
    company.status = Company.STATUS_ACTIVE

    db.add(company)
    await db.commit()
    await db.refresh(company)

    company = await _get_company(company.id, db)
    return {"data": _build_company_out(company)}


@router.get("/{company_id}", response_model=CompanyDetailOut)
async def show(
    company_id: int,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """
    Detalle de empresa con usuarios asignados, lista de beneficiarios
    y plantillas PDF disponibles. Equivale a show() en PHP.
    """
    result = await db.execute(
        select(Company)
        .options(
            selectinload(Company.users).selectinload(CompanyUser.user),
            selectinload(Company.commission_beneficiary),
        )
        .where(Company.id == company_id)
    )
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")

    # Usuarios asignados (ordenados)
    assigned_users = sorted(
        [_user_brief(cu.user) for cu in company.users if cu.user],
        key=lambda u: (u.display_name, u.email),
    )

    # Todos los usuarios como candidatos a beneficiario
    all_users_result = await db.execute(
        select(User).order_by(User.first_name, User.last_name, User.email)
    )
    beneficiary_users = [_user_brief(u) for u in all_users_result.scalars().all()]

    # Plantillas PDF disponibles
    pdf_result = await db.execute(
        select(Template)
        .where(
            func.upper(Template.type) == Template.TYPE_PDF.upper(),
            Template.deleted_at.is_(None),
        )
        .order_by(Template.name)
    )
    pdf_templates = [
        PdfTemplateOut(id=t.id, name=t.name) for t in pdf_result.scalars().all()
    ]

    return CompanyDetailOut(
        data=_build_company_out(company),
        assigned_users=assigned_users,
        beneficiary_users=beneficiary_users,
        branding_defaults=_branding_defaults(),
        pdf_templates=pdf_templates,
    )


@router.put("/{company_id}", response_model=dict)
async def update(
    company_id: int,
    body: UpdateCompanyRequest,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """
    Actualización parcial de empresa (equivale a update() con 'sometimes' en PHP).
    Maneja campos básicos, branding, sync de usuarios y beneficiario de comisión.
    """
    company = await _get_company(company_id, db)
    fields = body.model_fields_set

    if "name" in fields and body.name:
        company.name = body.name.strip()

    if "short_code" in fields and body.short_code:
        sc = body.short_code.strip().upper()
        clash = (await db.execute(
            select(Company).where(
                func.upper(Company.short_code) == sc,
                Company.id != company_id,
            )
        )).scalar_one_or_none()
        if clash:
            raise HTTPException(status_code=422, detail="El short_code ya existe.")
        company.short_code = sc

    for field in ("phone", "email", "description", "pdf_template_id"):
        if field in fields:
            setattr(company, field, getattr(body, field))

    if "status" in fields and body.status in _VALID_STATUSES:
        company.status = body.status

    if "commission_beneficiary_user_id" in fields:
        company.commission_beneficiary_user_id = body.commission_beneficiary_user_id

    # Branding: strip '#' antes de guardar
    for color_field in ("branding_text_dark", "branding_bg_light", "branding_text_light", "branding_bg_dark"):
        if color_field in fields:
            raw = getattr(body, color_field)
            setattr(company, color_field, raw.lstrip("#") if raw else None)

    # Sync de usuarios (reemplaza todos)
    if "users" in fields:
        await db.execute(delete(CompanyUser).where(CompanyUser.company_id == company_id))
        for uid in (body.users or []):
            db.add(CompanyUser(company_id=company_id, user_id=uid))

    await db.commit()
    company = await _get_company(company_id, db)
    return {"data": _build_company_out(company)}


# ─────────────────────────── Company: acciones de estado ─────────────────────

@router.put("/{company_id}/suspend", response_model=dict)
async def suspend(
    company_id: int,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Suspende una empresa (status → inactive). Equivale a suspend() en PHP."""
    company = await _get_company(company_id, db)
    if company.status != Company.STATUS_ARCHIVED:
        company.status = Company.STATUS_INACTIVE
        await db.commit()
        company = await _get_company(company_id, db)
    return {
        "data": _build_company_out(company),
        "toast": {"type": "success", "message": "Empresa suspendida correctamente."},
    }


@router.put("/{company_id}/archive", response_model=dict)
async def archive(
    company_id: int,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Archiva una empresa (status → archived). Equivale a archive() en PHP."""
    company = await _get_company(company_id, db)
    company.status = Company.STATUS_ARCHIVED
    await db.commit()
    company = await _get_company(company_id, db)
    return {
        "data": _build_company_out(company),
        "toast": {"type": "success", "message": "Empresa archivada correctamente."},
    }


@router.put("/{company_id}/activate", response_model=dict)
async def activate(
    company_id: int,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Activa una empresa (status → active). Equivale a activate() en PHP."""
    company = await _get_company(company_id, db)
    company.status = Company.STATUS_ACTIVE
    await db.commit()
    company = await _get_company(company_id, db)
    return {
        "data": _build_company_out(company),
        "toast": {"type": "success", "message": "Empresa activada correctamente."},
    }


# ─────────────────────────── Company: usuarios asignados ─────────────────────

@router.get("/{company_id}/users/search", response_model=PaginatedUsersOut)
async def search_users(
    company_id: int,
    search: str = Query(default=""),
    per_page: int = Query(default=10, ge=5, le=50),
    page: int = Query(default=1, ge=1),
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """
    Búsqueda paginada de usuarios para el modal de asignación.
    Equivale a searchUsers() en PHP.
    """
    # Verificar que la empresa existe
    await _get_company(company_id, db)

    q = select(User).where(User.status == "active", User.deleted_at.is_(None))
    search = search.strip()
    if search:
        q = q.where(User.email.ilike(f"%{search}%"))

    q = q.order_by(User.first_name, User.last_name, User.email)

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    last_page = max(1, math.ceil(total / per_page))

    items = list((await db.execute(q.offset((page - 1) * per_page).limit(per_page))).scalars().all())

    # IDs ya asignados a esta empresa
    attached_result = await db.execute(
        select(CompanyUser.user_id).where(CompanyUser.company_id == company_id)
    )
    attached_ids = {row[0] for row in attached_result.all()}

    data = [
        UserSearchItemOut(
            id=u.id,
            email=u.email,
            display_name=u.full_name,
            is_attached=u.id in attached_ids,
        )
        for u in items
    ]

    return PaginatedUsersOut(
        data=data,
        meta=PaginationMeta(current_page=page, last_page=last_page, per_page=per_page, total=total),
    )


@router.post("/{company_id}/users/{user_id}", response_model=dict)
async def attach_user(
    company_id: int,
    user_id: int,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """
    Asocia un usuario a una empresa (idempotente, syncWithoutDetaching).
    Equivale a attachUser() en PHP.
    """
    company = await _get_company(company_id, db)

    user_result = await db.execute(select(User).where(User.id == user_id))
    if user_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    already = (await db.execute(
        select(CompanyUser).where(
            CompanyUser.company_id == company_id,
            CompanyUser.user_id == user_id,
        )
    )).scalar_one_or_none()

    if already is None:
        db.add(CompanyUser(company_id=company_id, user_id=user_id))
        await db.commit()

    company = await _get_company(company_id, db)
    return {"data": _build_company_out(company)}


@router.delete("/{company_id}/users/{user_id}", response_model=dict)
async def detach_user(
    company_id: int,
    user_id: int,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """
    Desasocia un usuario de una empresa.
    Si era el beneficiario de comisiones, limpia esa referencia.
    Equivale a detachUser() en PHP.
    """
    company = await _get_company(company_id, db)

    if company.commission_beneficiary_user_id == user_id:
        company.commission_beneficiary_user_id = None
        await db.flush()

    await db.execute(
        delete(CompanyUser).where(
            CompanyUser.company_id == company_id,
            CompanyUser.user_id == user_id,
        )
    )
    await db.commit()

    company = await _get_company(company_id, db)
    return {"data": _build_company_out(company)}


# ─────────────────────────── Commission Users ────────────────────────────────

async def _get_commission_user(company_id: int, ccu_id: int, db: AsyncSession) -> CompanyCommissionUser:
    """Carga un CompanyCommissionUser verificando que pertenece a la empresa."""
    result = await db.execute(
        select(CompanyCommissionUser)
        .options(selectinload(CompanyCommissionUser.user))
        .where(
            CompanyCommissionUser.id == ccu_id,
            CompanyCommissionUser.company_id == company_id,
        )
    )
    ccu = result.scalar_one_or_none()
    if ccu is None:
        raise HTTPException(status_code=404, detail="Registro de comisión no encontrado.")
    return ccu


def _build_ccu_out(ccu: CompanyCommissionUser) -> CommissionUserOut:
    user = ccu.user
    return CommissionUserOut(
        id=ccu.id,
        user_id=ccu.user_id,
        commission=f"{float(ccu.commission or 0):.2f}",
        user=None if user is None else {
            "id": user.id,
            "email": user.email,
            "display_name": user.full_name,
        },
    )


@router.get("/{company_id}/commission-users/available", response_model=PaginatedAvailableUsersOut)
async def commission_users_available(
    company_id: int,
    q: str = Query(default=""),
    per_page: int = Query(default=20, ge=1),
    page: int = Query(default=1, ge=1),
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """
    Usuarios disponibles para añadir como beneficiarios de comisiones,
    con bandera 'attached'. Equivale a available() en PHP.
    """
    await _get_company(company_id, db)

    base_q = select(User).where(User.status == "active", User.deleted_at.is_(None))
    search = q.strip()
    if search:
        base_q = base_q.where(User.email.ilike(f"%{search}%"))

    base_q = base_q.order_by(User.first_name, User.last_name, User.email)

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    last_page = max(1, math.ceil(total / per_page))

    users = list((await db.execute(
        base_q.offset((page - 1) * per_page).limit(per_page)
    )).scalars().all())

    # Mapa user_id → ccu.id para los ya asignados
    assigned_result = await db.execute(
        select(CompanyCommissionUser).where(CompanyCommissionUser.company_id == company_id)
    )
    assigned_map = {row.user_id: row.id for row in assigned_result.scalars().all()}

    data = [
        AvailableUserItemOut(
            id=u.id,
            email=u.email,
            display_name=u.full_name,
            attached=u.id in assigned_map,
            commission_user_id=assigned_map.get(u.id),
        )
        for u in users
    ]

    return PaginatedAvailableUsersOut(
        data=data,
        meta=PaginationMeta(current_page=page, last_page=last_page, per_page=per_page, total=total),
    )


@router.get("/{company_id}/commission-users", response_model=dict)
async def commission_users_index(
    company_id: int,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Lista usuarios de comisiones de una empresa. Equivale a index() en PHP."""
    await _get_company(company_id, db)

    result = await db.execute(
        select(CompanyCommissionUser)
        .options(selectinload(CompanyCommissionUser.user))
        .where(CompanyCommissionUser.company_id == company_id)
        .order_by(CompanyCommissionUser.id)
    )
    rows = list(result.scalars().all())
    return {"data": [_build_ccu_out(r) for r in rows]}


@router.post("/{company_id}/commission-users", response_model=dict, status_code=201)
async def commission_users_store(
    company_id: int,
    body: StoreCommissionUserRequest,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """
    Añade un usuario a la lista de comisiones de la empresa.
    Equivale a store() en PHP.
    """
    await _get_company(company_id, db)

    user_result = await db.execute(select(User).where(User.id == body.user_id))
    if user_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    already = (await db.execute(
        select(CompanyCommissionUser).where(
            CompanyCommissionUser.company_id == company_id,
            CompanyCommissionUser.user_id == body.user_id,
        )
    )).scalar_one_or_none()

    if already is not None:
        raise HTTPException(
            status_code=422,
            detail="El usuario ya está asociado como beneficiario de comisiones en esta empresa.",
        )

    ccu = CompanyCommissionUser()
    ccu.company_id = company_id
    ccu.user_id = body.user_id
    ccu.commission = 0

    db.add(ccu)
    await db.commit()
    await db.refresh(ccu)

    ccu = await _get_commission_user(company_id, ccu.id, db)
    return {
        "data": _build_ccu_out(ccu),
        "toast": {"type": "success", "message": "Usuario añadido a la lista de comisiones."},
    }


@router.patch("/{company_id}/commission-users/{ccu_id}", response_model=dict)
async def commission_users_update(
    company_id: int,
    ccu_id: int,
    body: UpdateCommissionRequest,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """
    Actualiza la comisión de un usuario (autosave).
    Equivale a update() en PHP.
    """
    ccu = await _get_commission_user(company_id, ccu_id, db)
    ccu.commission = body.commission
    await db.commit()

    ccu = await _get_commission_user(company_id, ccu_id, db)
    return {
        "data": _build_ccu_out(ccu),
        "toast": {"type": "success", "message": "Comisión actualizada correctamente."},
    }


@router.delete("/{company_id}/commission-users/{ccu_id}", response_model=dict)
async def commission_users_destroy(
    company_id: int,
    ccu_id: int,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """
    Elimina un usuario de la lista de comisiones.
    Equivale a destroy() en PHP.
    """
    ccu = await _get_commission_user(company_id, ccu_id, db)
    await db.delete(ccu)
    await db.commit()
    return {"toast": {"type": "success", "message": "Usuario eliminado de la lista de comisiones."}}
