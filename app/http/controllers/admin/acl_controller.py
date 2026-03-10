from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.http.middleware.permission import require_permission
from app.http.requests.admin.acl_request import (
    MatrixDataOut,
    PermissionOut,
    RoleOut,
    StorePermissionRequest,
    StoreRoleRequest,
    ToggleAssignmentRequest,
    ToggleOut,
    UpdatePermissionRequest,
    UpdateRoleRequest,
)
from app.models.permission import Permission, role_has_permissions
from app.models.role import Role

router = APIRouter(prefix="/admin/acl/roles", tags=["admin:acl"])

_VALID_GUARDS = frozenset({"admin", "customer"})


def _validate_guard(guard: str) -> str:
    if guard not in _VALID_GUARDS:
        raise HTTPException(status_code=404, detail="Guard no válido.")
    return guard


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/{guard}/matrix", response_model=MatrixDataOut)
async def matrix_data(
    guard: str,
    _actor=Depends(require_permission("system.roles")),
    db: AsyncSession = Depends(get_db),
):
    """
    Datos de la matriz roles/permisos para un guard.
    Equivale a matrixData() en RolesPermissionsController.php.
    """
    _validate_guard(guard)

    roles_result = await db.execute(
        select(Role).where(Role.guard_name == guard).order_by(Role.name)
    )
    roles = list(roles_result.scalars().all())

    perms_result = await db.execute(
        select(Permission).where(Permission.guard_name == guard).order_by(Permission.name)
    )
    permissions = list(perms_result.scalars().all())

    # Construir matrix: {role_id: [permission_id, ...]}
    matrix: dict[int, list[int]] = {r.id: [] for r in roles}

    if roles and permissions:
        role_ids = [r.id for r in roles]
        perm_ids = [p.id for p in permissions]

        pivot_result = await db.execute(
            select(role_has_permissions).where(
                role_has_permissions.c.role_id.in_(role_ids),
                role_has_permissions.c.permission_id.in_(perm_ids),
            )
        )
        for row in pivot_result.all():
            matrix[row.role_id].append(row.permission_id)

    return MatrixDataOut(
        roles=[RoleOut.model_validate(r) for r in roles],
        permissions=[PermissionOut.model_validate(p) for p in permissions],
        matrix=matrix,
    )


@router.post("/{guard}/roles", response_model=RoleOut, status_code=201)
async def store_role(
    guard: str,
    body: StoreRoleRequest,
    _actor=Depends(require_permission("system.roles")),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea un rol para el guard indicado.
    Equivale a storeRole() en RolesPermissionsController.php.
    """
    _validate_guard(guard)

    existing = await db.execute(
        select(Role).where(Role.name == body.name, Role.guard_name == guard)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=422,
            detail="Ya existe un rol con ese nombre para este guard.",
        )

    role = Role()
    role.guard_name = guard
    role.name = body.name
    role.label = json.dumps(body.label) if body.label is not None else None
    role.scope = body.scope

    db.add(role)
    await db.commit()
    await db.refresh(role)

    return RoleOut.model_validate(role)


@router.put("/{guard}/roles/{role_id}", response_model=RoleOut)
async def update_role(
    guard: str,
    role_id: int,
    body: UpdateRoleRequest,
    _actor=Depends(require_permission("system.roles")),
    db: AsyncSession = Depends(get_db),
):
    """
    Actualiza un rol del guard indicado (partial update con model_fields_set).
    Equivale a updateRole() en RolesPermissionsController.php (usa 'sometimes').
    """
    _validate_guard(guard)

    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if role is None or role.guard_name != guard:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    if "name" in body.model_fields_set and body.name is not None:
        existing = await db.execute(
            select(Role).where(
                Role.name == body.name,
                Role.guard_name == guard,
                Role.id != role_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=422,
                detail="Ya existe un rol con ese nombre para este guard.",
            )
        role.name = body.name

    if "label" in body.model_fields_set:
        role.label = json.dumps(body.label) if body.label is not None else None

    if "scope" in body.model_fields_set:
        role.scope = body.scope

    await db.commit()
    await db.refresh(role)

    return RoleOut.model_validate(role)


@router.post("/{guard}/permissions", response_model=PermissionOut, status_code=201)
async def store_permission(
    guard: str,
    body: StorePermissionRequest,
    _actor=Depends(require_permission("system.roles")),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea un permiso para el guard indicado.
    Equivale a storePermission() en RolesPermissionsController.php.
    """
    _validate_guard(guard)

    existing = await db.execute(
        select(Permission).where(Permission.name == body.name, Permission.guard_name == guard)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=422,
            detail="Ya existe un permiso con ese nombre para este guard.",
        )

    permission = Permission()
    permission.guard_name = guard
    permission.name = body.name
    permission.description = body.description

    db.add(permission)
    await db.commit()
    await db.refresh(permission)

    return PermissionOut.model_validate(permission)


@router.put("/{guard}/permissions/{permission_id}", response_model=PermissionOut)
async def update_permission(
    guard: str,
    permission_id: int,
    body: UpdatePermissionRequest,
    _actor=Depends(require_permission("system.roles")),
    db: AsyncSession = Depends(get_db),
):
    """
    Actualiza un permiso del guard indicado (partial update con model_fields_set).
    Equivale a updatePermission() en RolesPermissionsController.php (usa 'sometimes').
    """
    _validate_guard(guard)

    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    permission = result.scalar_one_or_none()
    if permission is None or permission.guard_name != guard:
        raise HTTPException(status_code=404, detail="Permiso no encontrado.")

    if "name" in body.model_fields_set and body.name is not None:
        existing = await db.execute(
            select(Permission).where(
                Permission.name == body.name,
                Permission.guard_name == guard,
                Permission.id != permission_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=422,
                detail="Ya existe un permiso con ese nombre para este guard.",
            )
        permission.name = body.name

    if "description" in body.model_fields_set:
        permission.description = body.description

    await db.commit()
    await db.refresh(permission)

    return PermissionOut.model_validate(permission)


@router.post("/{guard}/toggle", response_model=ToggleOut)
async def toggle_assignment(
    guard: str,
    body: ToggleAssignmentRequest,
    _actor=Depends(require_permission("system.roles")),
    db: AsyncSession = Depends(get_db),
):
    """
    Toggle (asignar / revocar) un permiso para un rol concreto.
    Equivale a toggleAssignment() en RolesPermissionsController.php.
    """
    _validate_guard(guard)

    role_result = await db.execute(
        select(Role).where(Role.id == body.role_id, Role.guard_name == guard)
    )
    role = role_result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    perm_result = await db.execute(
        select(Permission).where(
            Permission.id == body.permission_id, Permission.guard_name == guard
        )
    )
    permission = perm_result.scalar_one_or_none()
    if permission is None:
        raise HTTPException(status_code=404, detail="Permiso no encontrado.")

    existing = await db.execute(
        select(role_has_permissions).where(
            role_has_permissions.c.role_id == role.id,
            role_has_permissions.c.permission_id == permission.id,
        )
    )
    has_perm = existing.first() is not None

    if body.value and not has_perm:
        await db.execute(
            role_has_permissions.insert().values(
                role_id=role.id,
                permission_id=permission.id,
            )
        )
        await db.commit()
    elif not body.value and has_perm:
        await db.execute(
            role_has_permissions.delete().where(
                role_has_permissions.c.role_id == role.id,
                role_has_permissions.c.permission_id == permission.id,
            )
        )
        await db.commit()

    return ToggleOut(message="Asignación rol/permisos actualizada correctamente.")
