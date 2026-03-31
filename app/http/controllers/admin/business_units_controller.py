"""
Controlador de unidades de negocio (admin).
Equivale a BusinessUnitApiController.php.

Endpoints Unit:
  GET    /admin/business-units/api/units                      → list
  POST   /admin/business-units/api/units                      → store
  GET    /admin/business-units/api/units/{id}                 → show
  GET    /admin/business-units/api/units/{id}/children        → children
  PATCH  /admin/business-units/api/units/{id}/basic           → updateBasic
  PATCH  /admin/business-units/api/units/{id}/status          → updateStatus
  POST   .../units/{id}/change-type                           → changeType
  POST   .../units/{id}/move                                  → move
  POST   .../units/{id}/branding                              → updateBranding

Endpoints Users / Roles:
  GET    .../users/active                                     → usersSearchActive
  GET    .../roles/unit                                       → rolesUnitScope

Endpoints Members:
  GET    .../units/{id}/members                               → members
  POST   .../units/{id}/members                               → memberLink
  POST   .../units/{id}/members/create-user                   → memberCreateUser
  PATCH  .../units/{id}/members/{mid}                         → memberUpdateRole
  PATCH  .../units/{id}/members/{mid}/status                  → memberUpdateStatus
  DELETE .../units/{id}/members/{mid}                         → memberRemove

Endpoints GSA Commissions:
  GET    .../units/{id}/gsa-commissions                       → gsaCommissions
  GET    .../units/{id}/gsa-commissions/available             → gsaCommissionsAvailable
  POST   .../units/{id}/gsa-commissions                       → gsaCommissionsStore
  PATCH  .../units/{id}/gsa-commissions/{cid}                 → gsaCommissionsUpdate
  DELETE .../units/{id}/gsa-commissions/{cid}                 → gsaCommissionsDestroy

Permiso: admin.business_units.manage
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.http.middleware.permission import require_permission
from app.http.requests.admin.business_unit_request import (
    ActiveUserOut,
    ActiveUsersResponse,
    AvailableGSAUserItem,
    ChangeTypeRequest,
    ChildrenResponse,
    CreateUserMemberRequest,
    CreateUserMemberResponse,
    GSACommissionDataResponse,
    GSACommissionOut,
    GSACommissionsResponse,
    LinkMemberRequest,
    MemberDataResponse,
    MemberOut,
    MembersResponse,
    MoveUnitRequest,
    PaginatedAvailableGSAResponse,
    PaginationMeta,
    RoleOut,
    RolesResponse,
    StoreGSACommissionRequest,
    StoreUnitRequest,
    UnitDataResponse,
    UnitDetailOut,
    UnitDetailResponse,
    UnitListResponse,
    UnitOut,
    UpdateBasicRequest,
    UpdateBrandingRequest,
    UpdateGSACommissionRequest,
    UpdateMemberRoleRequest,
    UpdateMemberStatusRequest,
    UpdateStatusRequest,
)
from app.models.business_unit import BusinessUnit
from app.models.business_unit_membership import BusinessUnitMembership
from app.models.regalia import Regalia
from app.models.role import Role
from app.models.user import User

router = APIRouter(prefix="/admin/business-units/api", tags=["admin:business-units"])

_PERMISSION = "admin.business_units.manage"


# ─────────────────────────── Helpers ─────────────────────────────────────────


async def _get_unit(unit_id: int, db: AsyncSession) -> BusinessUnit:
    r = await db.execute(
        select(BusinessUnit)
        .options(selectinload(BusinessUnit.memberships), selectinload(BusinessUnit.children))
        .where(BusinessUnit.id == unit_id)
    )
    unit = r.scalar_one_or_none()
    if unit is None:
        raise HTTPException(status_code=404, detail="Unidad de negocio no encontrada.")
    return unit


def _unit_out(u: BusinessUnit) -> UnitOut:
    return UnitOut(
        id=u.id,
        name=u.name,
        type=u.type,
        status=u.status,
        parent_id=u.parent_id,
        members_count=len(u.memberships) if u.memberships else 0,
        children_count=len(u.children) if u.children else 0,
    )


def _unit_detail_out(u: BusinessUnit) -> UnitDetailOut:
    return UnitDetailOut(
        id=u.id,
        name=u.name,
        type=u.type,
        status=u.status,
        parent_id=u.parent_id,
        members_count=len(u.memberships) if u.memberships else 0,
        children_count=len(u.children) if u.children else 0,
        branding_text_dark=u.branding_text_dark,
        branding_bg_light=u.branding_bg_light,
        branding_text_light=u.branding_text_light,
        branding_bg_dark=u.branding_bg_dark,
        branding_logo_file_id=u.branding_logo_file_id,
    )


def _member_out(m: BusinessUnitMembership) -> MemberOut:
    return MemberOut(
        id=m.id,
        business_unit_id=m.business_unit_id,
        user_id=m.user_id,
        role_id=m.role_id,
        status=m.status,
        user_email=m.user.email if m.user else None,
        user_display_name=m.user.full_name if m.user else None,
        role_name=m.role.name if m.role else None,
    )


def _pagination_meta(total: int, page: int, per_page: int) -> PaginationMeta:
    return PaginationMeta(
        current_page=page,
        last_page=max(1, math.ceil(total / per_page)),
        per_page=per_page,
        total=total,
    )


def _validate_parent_rules(unit_type: str, parent_id: int | None) -> None:
    """Valida reglas de jerarquía padre-hijo. Equivale a assertParentRules() en PHP."""
    if unit_type == "consolidator" and parent_id is not None:
        raise HTTPException(status_code=422, detail="Un consolidador no puede tener padre.")
    if unit_type == "freelance" and parent_id is not None:
        raise HTTPException(status_code=422, detail="Un freelance no puede tener padre.")
    if unit_type == "counter" and parent_id is None:
        raise HTTPException(status_code=422, detail="Un counter debe tener un padre.")


# ═════════════════════════════════════════════════════════════════════════════
# UNITS: CRUD
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/units", response_model=UnitListResponse)
async def list_units(
    type: str | None = Query(default=None),
    status: str = Query(default="active"),
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=200),
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> UnitListResponse:
    """Lista unidades por tipo con filtros de status y búsqueda."""
    base_q = select(BusinessUnit).options(
        selectinload(BusinessUnit.memberships), selectinload(BusinessUnit.children)
    )
    if type:
        base_q = base_q.where(BusinessUnit.type == type)

    if status in ("active", "inactive"):
        base_q = base_q.where(BusinessUnit.status == status)

    search = q.strip()
    if search:
        base_q = base_q.where(BusinessUnit.name.ilike(f"%{search}%"))

    base_q = base_q.order_by(BusinessUnit.name)

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    units = list(
        (await db.execute(base_q.offset((page - 1) * per_page).limit(per_page)))
        .scalars()
        .unique()
        .all()
    )

    return UnitListResponse(
        data=[_unit_out(u) for u in units],
        meta=_pagination_meta(total, page, per_page),
    )


@router.post("/units", response_model=UnitDataResponse, status_code=201)
async def store(
    body: StoreUnitRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> UnitDataResponse:
    """Crea una nueva unidad de negocio."""
    _validate_parent_rules(body.type, body.parent_id)

    if body.parent_id is not None:
        parent_r = await db.execute(select(BusinessUnit).where(BusinessUnit.id == body.parent_id))
        if parent_r.scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail="Unidad padre no encontrada.")

    unit = BusinessUnit()
    unit.name = body.name.strip()
    unit.type = body.type
    unit.status = "active"
    unit.parent_id = body.parent_id

    db.add(unit)
    await db.commit()

    unit = await _get_unit(unit.id, db)
    return UnitDataResponse(data=_unit_out(unit))


@router.get("/units/{unit_id}", response_model=UnitDetailResponse)
async def show(
    unit_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> UnitDetailResponse:
    """Detalle de una unidad."""
    unit = await _get_unit(unit_id, db)
    return UnitDetailResponse(data=_unit_detail_out(unit))


@router.get("/units/{unit_id}/children", response_model=ChildrenResponse)
async def children(
    unit_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> ChildrenResponse:
    """Hijos directos de una unidad."""
    unit = await _get_unit(unit_id, db)
    child_ids = [c.id for c in unit.children]

    if not child_ids:
        return ChildrenResponse(data=[])

    r = await db.execute(
        select(BusinessUnit)
        .options(selectinload(BusinessUnit.memberships), selectinload(BusinessUnit.children))
        .where(BusinessUnit.id.in_(child_ids))
        .order_by(BusinessUnit.name)
    )
    return ChildrenResponse(data=[_unit_out(c) for c in r.scalars().unique().all()])


@router.patch("/units/{unit_id}/basic", response_model=UnitDataResponse)
async def update_basic(
    unit_id: int,
    body: UpdateBasicRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> UnitDataResponse:
    """Actualiza el nombre de una unidad."""
    unit = await _get_unit(unit_id, db)
    unit.name = body.name.strip()
    await db.commit()
    unit = await _get_unit(unit_id, db)
    return UnitDataResponse(data=_unit_out(unit))


@router.patch("/units/{unit_id}/status", response_model=UnitDataResponse)
async def update_status(
    unit_id: int,
    body: UpdateStatusRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> UnitDataResponse:
    """Cambia el status de una unidad (active/inactive)."""
    unit = await _get_unit(unit_id, db)
    unit.status = body.status
    await db.commit()
    unit = await _get_unit(unit_id, db)
    return UnitDataResponse(data=_unit_out(unit))


# ═════════════════════════════════════════════════════════════════════════════
# CHANGE TYPE / MOVE / BRANDING
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/units/{unit_id}/change-type", response_model=UnitDataResponse)
async def change_type(
    unit_id: int,
    body: ChangeTypeRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> UnitDataResponse:
    """Cambia el tipo de una unidad con reglas de conversión."""
    unit = await _get_unit(unit_id, db)

    from_type = unit.type
    to_type = body.target_type

    if from_type == "freelance" and to_type == "office":
        unit.type = "office"
        unit.parent_id = None
    elif from_type == "office" and to_type == "consolidator":
        if unit.parent_id is not None:
            raise HTTPException(
                status_code=422,
                detail="Solo una office sin padre puede convertirse en consolidator.",
            )
        unit.type = "consolidator"
        unit.parent_id = None
    elif from_type == "office" and to_type == "office" and body.detach_parent:
        if unit.parent_id is None:
            raise HTTPException(status_code=422, detail="La office ya es independiente.")
        unit.parent_id = None
    elif from_type == "counter" and to_type == "office":
        unit.type = "office"
        unit.parent_id = None
    else:
        raise HTTPException(status_code=422, detail="Conversión no permitida.")

    _validate_parent_rules(unit.type, unit.parent_id)  # type: ignore[arg-type]

    await db.commit()
    unit = await _get_unit(unit_id, db)
    return UnitDataResponse(data=_unit_out(unit))


@router.post("/units/{unit_id}/move", response_model=UnitDataResponse)
async def move(
    unit_id: int,
    body: MoveUnitRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> UnitDataResponse:
    """Mueve una unidad a un nuevo padre en la jerarquía."""
    unit = await _get_unit(unit_id, db)

    new_parent: BusinessUnit | None = None
    if body.parent_id is not None:
        pr = await db.execute(select(BusinessUnit).where(BusinessUnit.id == body.parent_id))
        new_parent = pr.scalar_one_or_none()
        if new_parent is None:
            raise HTTPException(status_code=422, detail="Unidad padre no encontrada.")

    _validate_parent_rules(unit.type, body.parent_id)  # type: ignore[arg-type]

    if new_parent is not None:
        if new_parent.id == unit.id:
            raise HTTPException(status_code=422, detail="Parent inválido.")

        # Verificar referencia circular: recorrer ancestros del nuevo padre
        node_id: int | None = new_parent.parent_id
        visited: set[int] = {new_parent.id}
        while node_id is not None:
            if node_id == unit.id:
                raise HTTPException(status_code=422, detail="Parent inválido (ciclo).")
            if node_id in visited:
                break
            visited.add(node_id)
            nr = await db.execute(select(BusinessUnit.parent_id).where(BusinessUnit.id == node_id))
            row = nr.one_or_none()
            node_id = row[0] if row else None

    unit.parent_id = new_parent.id if new_parent else None
    await db.commit()
    unit = await _get_unit(unit_id, db)
    return UnitDataResponse(data=_unit_out(unit))


@router.post("/units/{unit_id}/branding", response_model=UnitDetailResponse)
async def update_branding(
    unit_id: int,
    body: UpdateBrandingRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> UnitDetailResponse:
    """Actualiza campos de branding (colores). Freelance no permite branding."""
    unit = await _get_unit(unit_id, db)

    if unit.type == "freelance":
        raise HTTPException(status_code=422, detail="Freelance no permite editar branding.")

    for field in (
        "branding_text_dark",
        "branding_bg_light",
        "branding_text_light",
        "branding_bg_dark",
    ):
        value = getattr(body, field, None)
        if value is not None:
            value = value.strip() or None
        setattr(unit, field, value)

    if body.remove_logo:
        unit.branding_logo_file_id = None

    await db.commit()
    unit = await _get_unit(unit_id, db)
    return UnitDetailResponse(data=_unit_detail_out(unit))


# ═════════════════════════════════════════════════════════════════════════════
# ACTIVE USERS / ROLES
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/users/active", response_model=ActiveUsersResponse)
async def users_search_active(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=200),
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> ActiveUsersResponse:
    """Lista usuarios admin activos para asignación de miembros."""
    base_q = select(User).where(
        User.realm == "admin",
        User.status == "active",
        User.deleted_at.is_(None),
    )

    search = q.strip()
    if search:
        like = f"%{search}%"
        base_q = base_q.where(
            User.email.ilike(like)
            | User.first_name.ilike(like)
            | User.last_name.ilike(like)
            | User.display_name.ilike(like)
        )

    base_q = base_q.order_by(User.email)
    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    users = list(
        (await db.execute(base_q.offset((page - 1) * per_page).limit(per_page))).scalars().all()
    )

    data = [
        ActiveUserOut(
            id=u.id,
            email=u.email,
            display_name=u.full_name,
            status=u.status,
        )
        for u in users
    ]
    return ActiveUsersResponse(data=data, meta=_pagination_meta(total, page, per_page))


@router.get("/roles/unit", response_model=RolesResponse)
async def roles_unit_scope(
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> RolesResponse:
    """Lista roles disponibles con scope=unit y guard=admin."""
    r = await db.execute(
        select(Role)
        .where(Role.scope == Role.SCOPE_UNIT, Role.guard_name == "admin")
        .order_by(Role.name)
    )
    roles = r.scalars().all()
    data = [
        RoleOut(
            id=role.id,
            name=role.name,
            scope=role.scope,
            level=role.level,
            role_name=role.role_name,
        )
        for role in roles
    ]
    return RolesResponse(data=data)


# ═════════════════════════════════════════════════════════════════════════════
# MEMBERS
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/units/{unit_id}/members", response_model=MembersResponse)
async def members(
    unit_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> MembersResponse:
    """Lista miembros de una unidad."""
    await _get_unit(unit_id, db)
    r = await db.execute(
        select(BusinessUnitMembership)
        .options(
            selectinload(BusinessUnitMembership.user), selectinload(BusinessUnitMembership.role)
        )
        .where(BusinessUnitMembership.business_unit_id == unit_id)
        .order_by(BusinessUnitMembership.id)
    )
    return MembersResponse(data=[_member_out(m) for m in r.scalars().all()])


@router.post("/units/{unit_id}/members", response_model=MemberDataResponse, status_code=201)
async def member_link(
    unit_id: int,
    body: LinkMemberRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> MemberDataResponse:
    """Vincula un usuario existente a la unidad."""
    await _get_unit(unit_id, db)

    # Validar usuario
    user_r = await db.execute(select(User).where(User.id == body.user_id, User.status == "active"))
    if user_r.scalar_one_or_none() is None:
        raise HTTPException(status_code=422, detail="Usuario no encontrado o inactivo.")

    # Verificar duplicado
    existing = await db.execute(
        select(BusinessUnitMembership).where(
            BusinessUnitMembership.business_unit_id == unit_id,
            BusinessUnitMembership.user_id == body.user_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="El usuario ya es miembro de esta unidad.")

    membership = BusinessUnitMembership()
    membership.business_unit_id = unit_id
    membership.user_id = body.user_id
    membership.role_id = body.role_id
    membership.status = "active"

    db.add(membership)
    await db.commit()

    r = await db.execute(
        select(BusinessUnitMembership)
        .options(
            selectinload(BusinessUnitMembership.user), selectinload(BusinessUnitMembership.role)
        )
        .where(BusinessUnitMembership.id == membership.id)
    )
    m = r.scalar_one()

    return MemberDataResponse(
        data=_member_out(m),
        toast={"type": "success", "message": "Miembro vinculado correctamente."},
    )


@router.post(
    "/units/{unit_id}/members/create-user", response_model=CreateUserMemberResponse, status_code=201
)
async def member_create_user(
    unit_id: int,
    body: CreateUserMemberRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> CreateUserMemberResponse:
    """Crea un nuevo usuario admin y lo vincula como miembro de la unidad."""
    unit = await _get_unit(unit_id, db)

    if unit.type == "freelance":
        raise HTTPException(
            status_code=422,
            detail="Freelance no permite crear usuarios desde esta unidad.",
        )

    # Validar rol (scope=unit, guard=admin)
    role_r = await db.execute(
        select(Role).where(
            Role.id == body.role_id,
            Role.guard_name == "admin",
            Role.scope == Role.SCOPE_UNIT,
        )
    )
    role = role_r.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=422, detail="Rol inválido o fuera de alcance.")

    # Verificar email no duplicado
    email = body.email.strip().lower()
    existing_user = await db.execute(select(User).where(User.email == email))
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="Ya existe un usuario con ese email.")

    first_name = body.first_name.strip()
    last_name = body.last_name.strip()
    if not first_name or not last_name or not email:
        raise HTTPException(
            status_code=422,
            detail="Nombre, apellido y correo son requeridos.",
        )

    # Crear usuario
    new_user = User()
    new_user.realm = "admin"
    new_user.email = email
    new_user.first_name = first_name
    new_user.last_name = last_name
    new_user.display_name = f"{first_name} {last_name}".strip()
    new_user.status = "active"
    new_user.password = ""

    db.add(new_user)
    await db.flush()

    # Crear membresía
    membership = BusinessUnitMembership()
    membership.business_unit_id = unit_id
    membership.user_id = new_user.id
    membership.role_id = role.id
    membership.status = "active"

    db.add(membership)
    await db.commit()

    # Recargar con relaciones
    r = await db.execute(
        select(BusinessUnitMembership)
        .options(
            selectinload(BusinessUnitMembership.user), selectinload(BusinessUnitMembership.role)
        )
        .where(BusinessUnitMembership.id == membership.id)
    )
    m = r.scalar_one()

    return CreateUserMemberResponse(
        data=_member_out(m),
        toast={"type": "success", "message": "Usuario creado y vinculado."},
    )


@router.patch("/units/{unit_id}/members/{membership_id}", response_model=MemberDataResponse)
async def member_update_role(
    unit_id: int,
    membership_id: int,
    body: UpdateMemberRoleRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> MemberDataResponse:
    """Actualiza el rol de un miembro."""
    r = await db.execute(
        select(BusinessUnitMembership)
        .options(
            selectinload(BusinessUnitMembership.user), selectinload(BusinessUnitMembership.role)
        )
        .where(
            BusinessUnitMembership.id == membership_id,
            BusinessUnitMembership.business_unit_id == unit_id,
        )
    )
    m = r.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Membresía no encontrada.")

    m.role_id = body.role_id
    await db.commit()

    r = await db.execute(
        select(BusinessUnitMembership)
        .options(
            selectinload(BusinessUnitMembership.user), selectinload(BusinessUnitMembership.role)
        )
        .where(BusinessUnitMembership.id == m.id)
    )
    m = r.scalar_one()

    return MemberDataResponse(
        data=_member_out(m),
        toast={"type": "success", "message": "Rol actualizado correctamente."},
    )


@router.patch("/units/{unit_id}/members/{membership_id}/status", response_model=MemberDataResponse)
async def member_update_status(
    unit_id: int,
    membership_id: int,
    body: UpdateMemberStatusRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> MemberDataResponse:
    """Cambia status de un miembro (active/inactive)."""
    r = await db.execute(
        select(BusinessUnitMembership)
        .options(
            selectinload(BusinessUnitMembership.user), selectinload(BusinessUnitMembership.role)
        )
        .where(
            BusinessUnitMembership.id == membership_id,
            BusinessUnitMembership.business_unit_id == unit_id,
        )
    )
    m = r.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Membresía no encontrada.")

    m.status = body.status
    await db.commit()
    await db.refresh(m)

    return MemberDataResponse(
        data=_member_out(m),
        toast={"type": "success", "message": "Estado de miembro actualizado."},
    )


@router.delete("/units/{unit_id}/members/{membership_id}", response_model=dict)
async def member_remove(
    unit_id: int,
    membership_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Elimina un miembro de la unidad."""
    r = await db.execute(
        select(BusinessUnitMembership).where(
            BusinessUnitMembership.id == membership_id,
            BusinessUnitMembership.business_unit_id == unit_id,
        )
    )
    m = r.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Membresía no encontrada.")

    await db.delete(m)
    await db.commit()
    return {"toast": {"type": "success", "message": "Miembro eliminado de la unidad."}}


# ═════════════════════════════════════════════════════════════════════════════
# GSA COMMISSIONS (Regalías de la unidad)
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/units/{unit_id}/gsa-commissions", response_model=GSACommissionsResponse)
async def gsa_commissions(
    unit_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> GSACommissionsResponse:
    """Lista regalías (tipo unit) vinculadas a esta unidad."""
    await _get_unit(unit_id, db)
    r = await db.execute(
        select(Regalia)
        .options(selectinload(Regalia.beneficiary))
        .where(Regalia.source_type == "unit", Regalia.source_id == unit_id)
        .order_by(Regalia.id)
    )
    items = []
    for reg in r.scalars().all():
        items.append(
            GSACommissionOut(
                id=reg.id,
                source_type=reg.source_type,
                source_id=reg.source_id,
                beneficiary_user_id=reg.beneficiary_user_id,
                commission=float(reg.commission) if reg.commission is not None else None,
                user_email=reg.beneficiary.email if reg.beneficiary else None,
                user_display_name=reg.beneficiary.full_name if reg.beneficiary else None,
            )
        )
    return GSACommissionsResponse(data=items)


@router.get(
    "/units/{unit_id}/gsa-commissions/available", response_model=PaginatedAvailableGSAResponse
)
async def gsa_commissions_available(
    unit_id: int,
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=200),
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedAvailableGSAResponse:
    """Usuarios disponibles para comisiones GSA."""
    await _get_unit(unit_id, db)

    base_q = select(User).where(
        User.realm == "admin", User.status == "active", User.deleted_at.is_(None)
    )
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

    assigned_r = await db.execute(
        select(Regalia.beneficiary_user_id).where(
            Regalia.source_type == "unit", Regalia.source_id == unit_id
        )
    )
    assigned_ids = {row[0] for row in assigned_r.all()}

    data = [
        AvailableGSAUserItem(
            id=u.id,
            email=u.email,
            display_name=u.full_name,
            is_assigned=u.id in assigned_ids,
        )
        for u in users
    ]
    return PaginatedAvailableGSAResponse(data=data, meta=_pagination_meta(total, page, per_page))


@router.post(
    "/units/{unit_id}/gsa-commissions", response_model=GSACommissionDataResponse, status_code=201
)
async def gsa_commissions_store(
    unit_id: int,
    body: StoreGSACommissionRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> GSACommissionDataResponse:
    """Crea una regalía (comisión GSA) para esta unidad."""
    await _get_unit(unit_id, db)

    user_r = await db.execute(select(User).where(User.id == body.user_id, User.status == "active"))
    user = user_r.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=422, detail="Usuario no encontrado o inactivo.")

    # Duplicado
    dup = await db.execute(
        select(Regalia).where(
            Regalia.source_type == "unit",
            Regalia.source_id == unit_id,
            Regalia.beneficiary_user_id == body.user_id,
        )
    )
    if dup.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="El usuario ya tiene comisión en esta unidad.")

    reg = Regalia()
    reg.source_type = "unit"
    reg.source_id = unit_id
    reg.beneficiary_user_id = body.user_id
    reg.commission = 0

    db.add(reg)
    await db.commit()
    await db.refresh(reg)

    return GSACommissionDataResponse(
        data=GSACommissionOut(
            id=reg.id,
            source_type=reg.source_type,
            source_id=reg.source_id,
            beneficiary_user_id=reg.beneficiary_user_id,
            commission=0,
            user_email=user.email,
            user_display_name=user.full_name,
        ),
        toast={"type": "success", "message": "Comisión GSA creada."},
    )


@router.patch(
    "/units/{unit_id}/gsa-commissions/{regalia_id}", response_model=GSACommissionDataResponse
)
async def gsa_commissions_update(
    unit_id: int,
    regalia_id: int,
    body: UpdateGSACommissionRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> GSACommissionDataResponse:
    """Actualiza comisión GSA."""
    r = await db.execute(
        select(Regalia)
        .options(selectinload(Regalia.beneficiary))
        .where(
            Regalia.id == regalia_id, Regalia.source_type == "unit", Regalia.source_id == unit_id
        )
    )
    reg = r.scalar_one_or_none()
    if reg is None:
        raise HTTPException(status_code=404, detail="Comisión no encontrada.")

    if "commission" in body.model_fields_set:
        reg.commission = body.commission

    await db.commit()
    await db.refresh(reg)

    return GSACommissionDataResponse(
        data=GSACommissionOut(
            id=reg.id,
            source_type=reg.source_type,
            source_id=reg.source_id,
            beneficiary_user_id=reg.beneficiary_user_id,
            commission=float(reg.commission) if reg.commission is not None else None,
            user_email=reg.beneficiary.email if reg.beneficiary else None,
            user_display_name=reg.beneficiary.full_name if reg.beneficiary else None,
        ),
        toast={"type": "success", "message": "Comisión actualizada."},
    )


@router.delete("/units/{unit_id}/gsa-commissions/{regalia_id}", response_model=dict)
async def gsa_commissions_destroy(
    unit_id: int,
    regalia_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Elimina una comisión GSA."""
    r = await db.execute(
        select(Regalia).where(
            Regalia.id == regalia_id, Regalia.source_type == "unit", Regalia.source_id == unit_id
        )
    )
    reg = r.scalar_one_or_none()
    if reg is None:
        raise HTTPException(status_code=404, detail="Comisión no encontrada.")

    await db.delete(reg)
    await db.commit()
    return {"toast": {"type": "success", "message": "Comisión eliminada."}}
