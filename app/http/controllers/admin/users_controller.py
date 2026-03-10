from __future__ import annotations

import math
import secrets
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.http.middleware.permission import require_permission
from app.http.requests.admin.user_request import (
    CreateUserRequest,
    PaginatedUsersOut,
    SearchUserItem,
    SearchUsersOut,
    StaffProfileOut,
    UpdateStatusRequest,
    UpdateUserRequest,
    UserDetailOut,
    UserOut,
)
from app.models.permission import USER_MODEL_TYPE, model_has_roles
from app.models.role import Role
from app.models.staff_profile import StaffProfile
from app.models.user import User
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/admin/users", tags=["admin:users"])


# ── Helpers privados ──────────────────────────────────────────────────────────


def _make_temp_password() -> str:
    """Genera y hashea una contraseña temporal aleatoria."""
    plain = secrets.token_urlsafe(16)
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _validate_vendor_commissions(roles: list[str], data: dict) -> dict[str, str]:
    """
    Valida que los roles vendedor_* tengan sus comisiones configuradas.
    Equivale a UsersController::validateVendorCommissions() de PHP.
    """
    errors: dict[str, str] = {}
    if "vendedor_regular" in roles:
        if data.get("commission_regular_first_year_pct") is None:
            errors["commission_regular_first_year_pct"] = "Obligatorio para vendedor regular."
        if data.get("commission_regular_renewal_pct") is None:
            errors["commission_regular_renewal_pct"] = "Obligatorio para vendedor regular."
    if "vendedor_capitados" in roles:
        if data.get("commission_capitados_pct") is None:
            errors["commission_capitados_pct"] = "Obligatorio para vendedor capitados."
    return errors


async def _sync_roles(db: AsyncSession, user: User, role_names: list[str]) -> None:
    """
    Sincroniza los roles del usuario al conjunto exacto de role_names.
    Equivale a $user->syncRoles() de Spatie.
    """
    svc = PermissionService(db)
    current_roles = await svc.get_roles(user)
    current_map = {r.name: r for r in current_roles}
    target_names = set(role_names)

    # Remover roles que ya no aplican
    for name, role in current_map.items():
        if name not in target_names:
            await svc.remove_role(user, role)

    # Agregar roles nuevos
    if role_names:
        result = await db.execute(
            select(Role).where(
                Role.name.in_(role_names),
                Role.guard_name == "admin",
            )
        )
        for role in result.scalars().all():
            if role.name not in current_map:
                await svc.assign_role(user, role)


async def _load_roles_for_users(
    db: AsyncSession, user_ids: list[int]
) -> dict[int, list[str]]:
    """Carga los roles de múltiples usuarios en una sola query (evita N+1)."""
    if not user_ids:
        return {}
    result = await db.execute(
        select(Role.name, model_has_roles.c.model_id)
        .join(model_has_roles, Role.id == model_has_roles.c.role_id)
        .where(
            model_has_roles.c.model_id.in_(user_ids),
            model_has_roles.c.model_type == USER_MODEL_TYPE,
        )
    )
    roles_map: dict[int, list[str]] = {uid: [] for uid in user_ids}
    for role_name, uid in result.all():
        roles_map[uid].append(role_name)
    return roles_map


def _build_user_out(
    user: User,
    roles: list[str],
    staff_profile: StaffProfile | None = None,
) -> UserDetailOut:
    """Construye un UserDetailOut a partir de un User ORM y sus datos relacionados."""
    return UserDetailOut(
        id=user.id,
        realm=user.realm,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        display_name=user.display_name,
        status=user.status,
        force_password_change=bool(user.force_password_change),
        created_at=user.created_at,
        updated_at=user.updated_at,
        deleted_at=user.deleted_at,
        roles=roles,
        staff_profile=StaffProfileOut.model_validate(staff_profile) if staff_profile else None,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedUsersOut)
async def index(
    q: str | None = Query(None),
    filter_status: str | None = Query(None, alias="status"),
    role: str | None = Query(None),
    per_page: int = Query(15, ge=1, le=100),
    page: int = Query(1, ge=1),
    _actor: User = Depends(require_permission("users.viewAny")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedUsersOut:
    """
    GET /admin/users — lista paginada de usuarios admin con filtros.
    Equivale a UsersController::index() de PHP.
    """
    base_q = select(User).where(User.realm == "admin", User.deleted_at.is_(None))

    if filter_status:
        base_q = base_q.where(User.status == filter_status)

    if q:
        like = f"%{q}%"
        base_q = base_q.where(
            or_(
                User.first_name.like(like),
                User.last_name.like(like),
                User.display_name.like(like),
                User.email.like(like),
            )
        )

    if role:
        role_subq = (
            select(model_has_roles.c.model_id)
            .join(Role, Role.id == model_has_roles.c.role_id)
            .where(
                Role.name == role,
                Role.guard_name == "admin",
                model_has_roles.c.model_type == USER_MODEL_TYPE,
            )
            .scalar_subquery()
        )
        base_q = base_q.where(User.id.in_(role_subq))

    # Contar total
    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar_one()

    # Paginar
    offset = (page - 1) * per_page
    result = await db.execute(base_q.order_by(User.id.desc()).offset(offset).limit(per_page))
    users = list(result.scalars().all())

    # Cargar roles en batch
    roles_map = await _load_roles_for_users(db, [u.id for u in users])

    last_page = max(1, math.ceil(total / per_page)) if total else 1

    data = [
        UserOut(
            id=u.id,
            realm=u.realm,
            email=u.email,
            first_name=u.first_name,
            last_name=u.last_name,
            display_name=u.display_name,
            status=u.status,
            force_password_change=bool(u.force_password_change),
            created_at=u.created_at,
            updated_at=u.updated_at,
            deleted_at=u.deleted_at,
            roles=roles_map.get(u.id, []),
        )
        for u in users
    ]

    return PaginatedUsersOut(
        data=data,
        meta={
            "pagination": {
                "current_page": page,
                "last_page": last_page,
                "per_page": per_page,
                "total": total,
                "from": offset + 1 if users else 0,
                "to": offset + len(users),
            }
        },
    )


@router.get("/search", response_model=SearchUsersOut)
async def search(
    q: str = Query(""),
    filter_status: str | None = Query(None, alias="status"),
    per_page: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    _actor: User = Depends(require_permission("users.viewAny")),
    db: AsyncSession = Depends(get_db),
) -> SearchUsersOut:
    """
    GET /admin/users/search — buscador para componentes de autocompletado.
    Equivale a UsersController::apiSearch() de PHP.
    """
    base_q = select(User).where(User.realm == "admin", User.deleted_at.is_(None))

    if filter_status:
        base_q = base_q.where(User.status == filter_status)

    if q.strip():
        like = f"%{q.strip()}%"
        base_q = base_q.where(
            or_(
                User.first_name.like(like),
                User.last_name.like(like),
                User.display_name.like(like),
                User.email.like(like),
            )
        )

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar_one()

    offset = (page - 1) * per_page
    result = await db.execute(
        base_q.order_by(User.display_name, User.id).offset(offset).limit(per_page)
    )
    users = list(result.scalars().all())

    last_page = max(1, math.ceil(total / per_page)) if total else 1

    data = [
        SearchUserItem(
            id=u.id,
            display_name=u.display_name or f"{u.first_name} {u.last_name or ''}".strip(),
            email=u.email,
            status=u.status,
        )
        for u in users
    ]

    return SearchUsersOut(
        data=data,
        meta={
            "pagination": {
                "current_page": page,
                "last_page": last_page,
                "per_page": per_page,
                "total": total,
                "from": offset + 1 if users else 0,
                "to": offset + len(users),
            }
        },
    )


@router.post("", response_model=UserDetailOut, status_code=status.HTTP_201_CREATED)
async def store(
    body: CreateUserRequest,
    _actor: User = Depends(require_permission("users.create")),
    db: AsyncSession = Depends(get_db),
) -> UserDetailOut:
    """
    POST /admin/users — crea un usuario admin con contraseña temporal.
    Equivale a UsersController::store() de PHP.
    """
    # Verificar unicidad de email en realm admin
    existing = await db.execute(
        select(User).where(
            User.email == body.email,
            User.realm == "admin",
            User.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"email": "El email ya está registrado en este dominio."},
        )

    # Validar comisiones según roles vendedor_*
    commission_errors = _validate_vendor_commissions(
        body.roles,
        {
            "commission_regular_first_year_pct": body.commission_regular_first_year_pct,
            "commission_regular_renewal_pct": body.commission_regular_renewal_pct,
            "commission_capitados_pct": body.commission_capitados_pct,
        },
    )
    if commission_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=commission_errors,
        )

    # Crear usuario con contraseña temporal y force_password_change=True
    user = User(
        realm="admin",
        first_name=body.first_name,
        last_name=body.last_name or "",
        display_name=body.display_name,
        email=body.email,
        status=body.status,
        password=_make_temp_password(),
        force_password_change=True,
    )
    db.add(user)
    await db.flush()  # genera user.id antes de los roles

    # Asignar roles
    if body.roles:
        await _sync_roles(db, user, body.roles)

    # Staff profile (solo si se enviaron datos)
    staff_profile: StaffProfile | None = None
    profile_fields = [
        body.work_phone,
        body.commission_regular_first_year_pct,
        body.commission_regular_renewal_pct,
        body.commission_capitados_pct,
    ]
    if any(f is not None for f in profile_fields):
        staff_profile = StaffProfile(
            user_id=user.id,
            work_phone=body.work_phone,
            commission_regular_first_year_pct=body.commission_regular_first_year_pct,
            commission_regular_renewal_pct=body.commission_regular_renewal_pct,
            commission_capitados_pct=body.commission_capitados_pct,
        )
        db.add(staff_profile)

    await db.commit()
    await db.refresh(user)

    return _build_user_out(user, body.roles, staff_profile)


@router.get("/{user_id}", response_model=UserDetailOut)
async def show(
    user_id: int,
    _actor: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
) -> UserDetailOut:
    """
    GET /admin/users/{id} — detalle de usuario con roles y staff_profile.
    Equivale a UsersController::show() de PHP.
    """
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.realm == "admin",
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    svc = PermissionService(db)
    role_names = [r.name for r in await svc.get_roles(user)]

    profile_r = await db.execute(
        select(StaffProfile).where(StaffProfile.user_id == user_id)
    )
    staff_profile = profile_r.scalar_one_or_none()

    return _build_user_out(user, role_names, staff_profile)


@router.put("/{user_id}", response_model=UserDetailOut)
async def update(
    user_id: int,
    body: UpdateUserRequest,
    _actor: User = Depends(require_permission("users.update")),
    db: AsyncSession = Depends(get_db),
) -> UserDetailOut:
    """
    PUT /admin/users/{id} — actualiza datos, staff_profile y roles.
    Equivale a UsersController::update() de PHP.
    """
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.realm == "admin",
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    # Verificar unicidad de email (ignorar el propio usuario)
    email_check = await db.execute(
        select(User).where(
            User.email == body.email,
            User.realm == "admin",
            User.id != user_id,
            User.deleted_at.is_(None),
        )
    )
    if email_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"email": "El email ya está registrado en este dominio."},
        )

    # Validar comisiones si se pasan roles
    if body.roles is not None:
        commission_errors = _validate_vendor_commissions(
            body.roles,
            {
                "commission_regular_first_year_pct": body.commission_regular_first_year_pct,
                "commission_regular_renewal_pct": body.commission_regular_renewal_pct,
                "commission_capitados_pct": body.commission_capitados_pct,
            },
        )
        if commission_errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=commission_errors,
            )

    # Actualizar campos del usuario
    user.first_name = body.first_name
    user.last_name = body.last_name
    user.display_name = body.display_name if body.display_name is not None else user.display_name
    user.email = body.email
    user.status = body.status

    # Upsert staff_profile
    profile_r = await db.execute(
        select(StaffProfile).where(StaffProfile.user_id == user_id)
    )
    staff_profile = profile_r.scalar_one_or_none()
    if staff_profile is None:
        staff_profile = StaffProfile(user_id=user_id)
        db.add(staff_profile)

    staff_profile.work_phone = body.work_phone if body.work_phone is not None else staff_profile.work_phone
    staff_profile.notes_admin = body.notes_admin if body.notes_admin is not None else staff_profile.notes_admin
    staff_profile.commission_regular_first_year_pct = body.commission_regular_first_year_pct
    staff_profile.commission_regular_renewal_pct = body.commission_regular_renewal_pct
    staff_profile.commission_capitados_pct = body.commission_capitados_pct

    # Sincronizar roles si se enviaron
    if body.roles is not None:
        await _sync_roles(db, user, body.roles)
        final_roles = body.roles
    else:
        svc = PermissionService(db)
        final_roles = [r.name for r in await svc.get_roles(user)]

    await db.commit()
    await db.refresh(user)

    return _build_user_out(user, final_roles, staff_profile)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(
    user_id: int,
    _actor: User = Depends(require_permission("users.delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    DELETE /admin/users/{id} — soft delete.
    Equivale a UsersController::destroy() de PHP.
    """
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.realm == "admin",
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    user.deleted_at = datetime.now(timezone.utc)
    await db.commit()


@router.post("/{user_id}/restore", response_model=UserDetailOut)
async def restore(
    user_id: int,
    _actor: User = Depends(require_permission("users.restore")),
    db: AsyncSession = Depends(get_db),
) -> UserDetailOut:
    """
    POST /admin/users/{id}/restore — restaura un usuario soft-deleted.
    Equivale a UsersController::restore() de PHP.
    """
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.realm == "admin",
            User.deleted_at.isnot(None),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado o no está eliminado.",
        )

    user.deleted_at = None
    await db.commit()
    await db.refresh(user)

    svc = PermissionService(db)
    role_names = [r.name for r in await svc.get_roles(user)]
    return _build_user_out(user, role_names)


@router.put("/{user_id}/status", response_model=UserDetailOut)
async def update_status(
    user_id: int,
    body: UpdateStatusRequest,
    _actor: User = Depends(require_permission("users.update")),
    db: AsyncSession = Depends(get_db),
) -> UserDetailOut:
    """
    PUT /admin/users/{id}/status — cambia el estado del usuario.
    Equivale a UsersController::updateStatus() de PHP.
    """
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.realm == "admin",
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    user.status = body.status
    await db.commit()
    await db.refresh(user)

    svc = PermissionService(db)
    role_names = [r.name for r in await svc.get_roles(user)]
    return _build_user_out(user, role_names)
