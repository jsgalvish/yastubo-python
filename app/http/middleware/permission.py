from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.http.middleware.auth import get_current_user
from app.models.user import User
from app.services.permission_service import PermissionService


def require_permission(permission: str):
    """
    FastAPI dependency factory que verifica un permiso global.

    Uso en un endpoint:
        user: User = Depends(require_permission("users.viewAny"))

    Equivale a: if (!$user->can('users.viewAny')) abort(403);
    """

    async def _check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        svc = PermissionService(db)
        if not await svc.user_can(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sin permiso: {permission}",
            )
        return user

    return _check


def require_role(role_name: str, guard_name: str | None = None):
    """
    FastAPI dependency factory que verifica un rol global.

    Uso en un endpoint:
        user: User = Depends(require_role("superadmin"))

    Equivale a: if (!$user->hasRole('superadmin')) abort(403);
    """

    async def _check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        svc = PermissionService(db)
        if not await svc.user_has_role(user, role_name, guard_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sin rol requerido: {role_name}",
            )
        return user

    return _check
