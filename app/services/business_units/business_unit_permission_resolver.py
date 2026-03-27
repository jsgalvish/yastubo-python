"""
Resuelve permisos efectivos de unidad de negocio para un usuario.

Equivale a App\\Services\\BusinessUnits\\BusinessUnitPermissionResolver de PHP.

Logica:
  1. Permisos globales: si el usuario tiene el permiso via Spatie -> LEVEL_GLOBAL.
  2. Permisos locales: si el usuario es miembro de la unidad con un rol
     que tiene el permiso -> LEVEL_LOCAL.
  3. Permisos heredados: si un ancestro tiene manage_children efectivo
     y ademas tiene el permiso local, sus permisos se propagan como LEVEL_INHERITED.

El nivel efectivo final es el max(global, heredado, local).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.business_unit import BusinessUnit
from app.models.business_unit_membership import BusinessUnitMembership
from app.models.role import Role
from app.services.business_units.business_unit_abilities import (
    BusinessUnitAbilities,
)

if TYPE_CHECKING:
    from app.models.user import User

# ── Constantes de nivel ────────────────────────────────────────────────────

LEVEL_NONE = 0
LEVEL_LOCAL = 1
LEVEL_INHERITED = 2
LEVEL_GLOBAL = 3

# ── Lista maestra de permisos de unidad ────────────────────────────────────

PERMISSION_KEYS: list[str] = [
    "unit.structure.view",
    "unit.structure.manage",
    "unit.basic.view",
    "unit.basic.edit",
    "unit.branding.view",
    "unit.branding.manage",
    "unit.members.view",
    "unit.members.invite",
    "unit.members.manage_roles",
    "unit.members.remove",
    "unit.manage_children",
    "unit.gsa.commission",
    "unit.products.sell",
]


def _empty_permissions() -> dict[str, int]:
    """Devuelve un dict de permisos inicializado en LEVEL_NONE."""
    return {key: LEVEL_NONE for key in PERMISSION_KEYS}


class BusinessUnitPermissionResolver:
    """
    Calcula los permisos efectivos de un usuario para cada unidad de negocio.

    Uso tipico:
        resolver = BusinessUnitPermissionResolver(db)
        await resolver.load_user(user)          # pre-calcula globales
        abilities = await resolver.for_unit(user, unit)
        if abilities.can('can_basic_edit'):
            ...
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        # Cache: user_id -> {perm_name: level}
        self._global_permissions: dict[int, dict[str, int]] = {}
        # Cache: user_id -> {unit_id: {perm_name: level}}
        self._unit_permissions_cache: dict[int, dict[int, dict[str, int]]] = {}

    # ── Carga del usuario ──────────────────────────────────────────────────

    async def load_user(self, user: User) -> None:
        """
        Pre-calcula los permisos globales del usuario (una vez por request).

        Requiere que user._permissions_cache ya este poblado
        (via PermissionService.load_permissions).
        """
        if user.id not in self._global_permissions:
            self._global_permissions[user.id] = self._build_global_permissions(user)

    def _build_global_permissions(self, user: User) -> dict[str, int]:
        """
        Construye el array de permisos globales:
        - Inicializa todo en LEVEL_NONE.
        - Por cada permiso de la lista maestra, marca LEVEL_GLOBAL si el usuario lo tiene.
        """
        permissions = _empty_permissions()
        for name in PERMISSION_KEYS:
            if user.can(name):
                permissions[name] = LEVEL_GLOBAL
        return permissions

    # ── Resolver para una unidad ───────────────────────────────────────────

    async def for_unit(
        self,
        user: User,
        unit: BusinessUnit | None = None,
    ) -> BusinessUnitAbilities:
        """
        Construye el objeto de habilidades para una unidad concreta
        o solo globales si unit es None.
        """
        await self.load_user(user)
        levels = await self._permission_levels_for_unit(user, unit)

        return BusinessUnitAbilities(
            permission_levels=levels,
            global_permission_levels=self._global_permissions[user.id],
            user=user,
            unit=unit,
        )

    async def _permission_levels_for_unit(
        self,
        user: User,
        unit: BusinessUnit | None = None,
    ) -> dict[str, int]:
        """
        Devuelve los niveles de permiso efectivos (0..3) para una unidad concreta.
        Si unit es None, devuelve solo los permisos globales.
        """
        # Sin unidad => solo globales
        if unit is None:
            return dict(self._global_permissions[user.id])

        key = int(unit.id)

        # Cache hit
        user_cache = self._unit_permissions_cache.get(user.id)
        if user_cache is not None and key in user_cache:
            return user_cache[key]

        # Cadena de ancestros (root -> ... -> unidad objetivo)
        chain = await self._load_ancestor_chain(unit)
        if not chain:
            chain = [unit]

        unit_ids = [u.id for u in chain]

        # Membresias del usuario en las unidades de la cadena
        result = await self._db.execute(
            select(BusinessUnitMembership)
            .options(
                selectinload(BusinessUnitMembership.role).selectinload(
                    Role.permissions
                )
            )
            .where(
                BusinessUnitMembership.user_id == user.id,
                BusinessUnitMembership.business_unit_id.in_(unit_ids),
            )
        )
        memberships_list = list(result.scalars().all())
        memberships_by_unit: dict[int, BusinessUnitMembership] = {
            m.business_unit_id: m for m in memberships_list
        }

        # Permisos locales por unidad
        local_perms_by_unit_id: dict[int, list[str]] = {}
        for u in chain:
            local_names: list[str] = []
            membership = memberships_by_unit.get(u.id)
            if membership is not None and membership.role is not None:
                for perm in membership.role.permissions:
                    name = str(perm.name)
                    if name in PERMISSION_KEYS:
                        local_names.append(name)
            local_perms_by_unit_id[u.id] = local_names

        # Calcular niveles efectivos recorriendo la cadena
        perm_levels_by_unit_id: dict[int, dict[str, int]] = {}

        for index, u in enumerate(chain):
            # Base: permisos globales
            levels = dict(self._global_permissions[user.id])

            # 1) Permisos locales en esta unidad
            for perm_name in local_perms_by_unit_id[u.id]:
                current = levels.get(perm_name, LEVEL_NONE)
                if current < LEVEL_LOCAL:
                    levels[perm_name] = LEVEL_LOCAL

            # 2) Permisos heredados desde ancestros con manage_children efectivo
            if index > 0:
                for j in range(index):
                    anc = chain[j]
                    anc_id = int(anc.id)

                    anc_levels = perm_levels_by_unit_id.get(
                        anc_id, self._global_permissions[user.id]
                    )
                    manage_children_level = anc_levels.get(
                        "unit.manage_children", LEVEL_NONE
                    )

                    if manage_children_level > LEVEL_NONE:
                        for perm_name in local_perms_by_unit_id[anc_id]:
                            current = levels.get(perm_name, LEVEL_NONE)
                            if current < LEVEL_INHERITED:
                                levels[perm_name] = LEVEL_INHERITED

            perm_levels_by_unit_id[int(u.id)] = levels

        final = perm_levels_by_unit_id.get(key, dict(self._global_permissions[user.id]))

        # Guardar en cache
        if user.id not in self._unit_permissions_cache:
            self._unit_permissions_cache[user.id] = {}
        self._unit_permissions_cache[user.id][key] = final

        return final

    # ── Helpers ─────────────────────────────────────────────────────────────

    async def _load_ancestor_chain(self, unit: BusinessUnit) -> list[BusinessUnit]:
        """
        Carga la cadena de ancestros [raiz, ..., padre, unit].

        Hace eager load del parent para recorrer el arbol hacia arriba
        sin generar N+1 queries.
        """
        # Primero recolectamos los IDs subiendo por parent_id
        chain_ids: list[int] = []
        visited: set[int] = set()
        current: BusinessUnit | None = unit

        # Subimos por parent cargando cada nivel si hace falta
        while current is not None:
            if current.id in visited:
                break
            visited.add(current.id)
            chain_ids.insert(0, current.id)

            # Si el parent no esta cargado, lo cargamos
            if current.parent_id is not None and current.parent_id not in visited:
                result = await self._db.execute(
                    select(BusinessUnit).where(BusinessUnit.id == current.parent_id)
                )
                current = result.scalar_one_or_none()
            else:
                current = None

        # Ahora cargamos todas las unidades de la cadena de una sola vez
        if not chain_ids:
            return [unit]

        result = await self._db.execute(
            select(BusinessUnit).where(BusinessUnit.id.in_(chain_ids))
        )
        units_by_id = {u.id: u for u in result.scalars().all()}

        # Preservar orden: raiz -> ... -> unit
        return [units_by_id[uid] for uid in chain_ids if uid in units_by_id]
