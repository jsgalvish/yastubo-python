from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.permission import (
    USER_MODEL_TYPE,
    Permission,
    model_has_permissions,
    model_has_roles,
    role_has_permissions,
)
from app.models.role import Role
from app.models.user import User


class PermissionService:
    """
    Servicio de roles y permisos.
    Equivale a la capa Spatie\\Permission de PHP, adaptada para async.

    Patrón de uso con las dependencias FastAPI:
      1. Llamar a load_roles(user) y/o load_permissions(user)
         para poblar los caches del usuario.
      2. Luego usar user.has_role() y user.can() que leen esos caches.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Queries ───────────────────────────────────────────────────────────────

    async def get_roles(self, user: User) -> list[Role]:
        """Devuelve los roles asignados al usuario."""
        result = await self._db.execute(
            select(Role)
            .join(model_has_roles, Role.id == model_has_roles.c.role_id)
            .where(
                model_has_roles.c.model_id == user.id,
                model_has_roles.c.model_type == USER_MODEL_TYPE,
            )
        )
        return list(result.scalars().all())

    async def get_permissions(self, user: User) -> set[str]:
        """
        Devuelve todos los nombres de permiso del usuario
        (directos + heredados vía roles).
        """
        perms: set[str] = set()

        # Permisos directos (model_has_permissions)
        result = await self._db.execute(
            select(Permission)
            .join(
                model_has_permissions,
                Permission.id == model_has_permissions.c.permission_id,
            )
            .where(
                model_has_permissions.c.model_id == user.id,
                model_has_permissions.c.model_type == USER_MODEL_TYPE,
            )
        )
        perms.update(p.name for p in result.scalars().all())

        # Permisos heredados vía roles
        result = await self._db.execute(
            select(Permission)
            .join(
                role_has_permissions,
                Permission.id == role_has_permissions.c.permission_id,
            )
            .join(
                model_has_roles,
                role_has_permissions.c.role_id == model_has_roles.c.role_id,
            )
            .where(
                model_has_roles.c.model_id == user.id,
                model_has_roles.c.model_type == USER_MODEL_TYPE,
            )
        )
        perms.update(p.name for p in result.scalars().all())

        return perms

    # ── Carga de caches en el usuario ─────────────────────────────────────────

    async def load_roles(self, user: User) -> None:
        """
        Carga los roles del usuario en user._roles_cache.
        Después se puede usar user.has_role() sin hits adicionales a la BD.
        """
        user._roles_cache = await self.get_roles(user)  # type: ignore[attr-defined]

    async def load_permissions(self, user: User) -> None:
        """
        Carga todos los permisos del usuario en user._permissions_cache.
        Después se puede usar user.can() sin hits adicionales a la BD.
        """
        user._permissions_cache = await self.get_permissions(user)  # type: ignore[attr-defined]

    # ── Checks directos (sin cache) ───────────────────────────────────────────

    async def user_can(self, user: User, permission_name: str) -> bool:
        """Verifica si el usuario tiene un permiso (consulta BD)."""
        perms = await self.get_permissions(user)
        return permission_name in perms

    async def user_has_role(
        self, user: User, role_name: str, guard_name: str | None = None
    ) -> bool:
        """Verifica si el usuario tiene un rol (consulta BD)."""
        roles = await self.get_roles(user)
        return any(
            r.name == role_name and (guard_name is None or r.guard_name == guard_name)
            for r in roles
        )

    # ── Mutaciones: asignar / revocar roles ──────────────────────────────────

    async def assign_role(self, user: User, role: Role) -> None:
        """Asigna un rol al usuario (idempotente)."""
        exists = await self._db.execute(
            select(model_has_roles).where(
                model_has_roles.c.role_id == role.id,
                model_has_roles.c.model_type == USER_MODEL_TYPE,
                model_has_roles.c.model_id == user.id,
            )
        )
        if exists.first() is None:
            await self._db.execute(
                model_has_roles.insert().values(
                    role_id=role.id,
                    model_type=USER_MODEL_TYPE,
                    model_id=user.id,
                )
            )

    async def remove_role(self, user: User, role: Role) -> None:
        """Revoca un rol del usuario."""
        await self._db.execute(
            model_has_roles.delete().where(
                model_has_roles.c.role_id == role.id,
                model_has_roles.c.model_type == USER_MODEL_TYPE,
                model_has_roles.c.model_id == user.id,
            )
        )

    # ── Mutaciones: permisos directos en usuario ──────────────────────────────

    async def give_permission(self, user: User, permission: Permission) -> None:
        """Asigna un permiso directo al usuario (idempotente)."""
        exists = await self._db.execute(
            select(model_has_permissions).where(
                model_has_permissions.c.permission_id == permission.id,
                model_has_permissions.c.model_type == USER_MODEL_TYPE,
                model_has_permissions.c.model_id == user.id,
            )
        )
        if exists.first() is None:
            await self._db.execute(
                model_has_permissions.insert().values(
                    permission_id=permission.id,
                    model_type=USER_MODEL_TYPE,
                    model_id=user.id,
                )
            )

    async def revoke_permission(self, user: User, permission: Permission) -> None:
        """Revoca un permiso directo del usuario."""
        await self._db.execute(
            model_has_permissions.delete().where(
                model_has_permissions.c.permission_id == permission.id,
                model_has_permissions.c.model_type == USER_MODEL_TYPE,
                model_has_permissions.c.model_id == user.id,
            )
        )

    # ── Mutaciones: permisos en roles ─────────────────────────────────────────

    async def give_permission_to_role(self, role: Role, permission: Permission) -> None:
        """Asigna un permiso a un rol (idempotente)."""
        exists = await self._db.execute(
            select(role_has_permissions).where(
                role_has_permissions.c.role_id == role.id,
                role_has_permissions.c.permission_id == permission.id,
            )
        )
        if exists.first() is None:
            await self._db.execute(
                role_has_permissions.insert().values(
                    role_id=role.id,
                    permission_id=permission.id,
                )
            )

    async def revoke_permission_from_role(self, role: Role, permission: Permission) -> None:
        """Revoca un permiso de un rol."""
        await self._db.execute(
            role_has_permissions.delete().where(
                role_has_permissions.c.role_id == role.id,
                role_has_permissions.c.permission_id == permission.id,
            )
        )
