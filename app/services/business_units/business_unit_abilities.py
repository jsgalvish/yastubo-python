"""
Habilidades de unidad de negocio para un usuario.

Equivale a App\\Services\\BusinessUnits\\BusinessUnitAbilities de PHP.

Cada habilidad se mapea a un permiso + nivel minimo (LEVEL_*).
La clase es sincrona: recibe los niveles ya calculados y evalua
las habilidades sin tocar la BD.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.business_unit import BusinessUnit
    from app.models.user import User

# Constantes de nivel (re-exportadas desde el resolver para comodidad).
LEVEL_NONE = 0
LEVEL_LOCAL = 1
LEVEL_INHERITED = 2
LEVEL_GLOBAL = 3

# ── Mapa: habilidad => (nombre_permiso, nivel_minimo) ─────────────────────

ABILITY_PERMISSION_MAP: dict[str, tuple[str, int]] = {
    # Acceso global a la estructura (listado raiz, etc.)
    "can_structure_view":           ("unit.structure.view",        LEVEL_LOCAL),
    # Datos basicos
    "can_basic_view":               ("unit.basic.view",            LEVEL_LOCAL),
    "can_basic_edit":               ("unit.basic.edit",            LEVEL_LOCAL),
    # Branding
    "can_branding_view":            ("unit.branding.view",         LEVEL_LOCAL),
    "can_branding_manage":          ("unit.branding.manage",       LEVEL_LOCAL),
    # Miembros
    "can_members_view":             ("unit.members.view",          LEVEL_LOCAL),
    "can_members_invite":           ("unit.members.invite",        LEVEL_LOCAL),
    "can_members_manage_roles":     ("unit.members.manage_roles",  LEVEL_LOCAL),
    "can_members_manage_roles_any": ("unit.members.manage_roles",  LEVEL_INHERITED),
    "can_members_remove":           ("unit.members.remove",        LEVEL_INHERITED),
    # Hijos (estructura)
    "can_manage_children":          ("unit.manage_children",       LEVEL_LOCAL),
    # Estado de la unidad
    "can_toggle_status":            ("unit.structure.manage",      LEVEL_INHERITED),
    # Operaciones globales sobre estructura
    "can_move":                     ("unit.structure.manage",      LEVEL_GLOBAL),
    "can_change_type":              ("unit.structure.manage",      LEVEL_GLOBAL),
    "can_create":                   ("unit.structure.manage",      LEVEL_GLOBAL),
    # Operaciones globales sobre usuarios
    "can_pick_active_users":        ("unit.members.invite",        LEVEL_GLOBAL),
    "can_products_sell":            ("unit.products.sell",          LEVEL_GLOBAL),
    "can_access":                   ("unit.structure.view",        LEVEL_LOCAL),
    # GSA
    "can_edit_gsa_commission":      ("unit.gsa.commission",        LEVEL_GLOBAL),
}


class BusinessUnitAbilities:
    """
    Objeto de habilidades para una unidad concreta (o solo globales).

    Se construye con los niveles de permiso efectivos (0..3) ya calculados
    por BusinessUnitPermissionResolver.
    """

    __slots__ = (
        "_abilities_cache",
        "_global_permission_levels",
        "_permission_levels",
        "_unit",
        "_user",
    )

    def __init__(
        self,
        permission_levels: dict[str, int],
        global_permission_levels: dict[str, int],
        user: User | None = None,
        unit: BusinessUnit | None = None,
    ) -> None:
        self._permission_levels = permission_levels
        self._global_permission_levels = global_permission_levels
        self._user = user
        self._unit = unit
        self._abilities_cache: dict[str, bool] = {}

    # ── Nivel de permiso ───────────────────────────────────────────────────

    def permission_level(self, permission: str) -> int:
        """Nivel 0..3 de un permiso concreto."""
        return self._permission_levels.get(permission, LEVEL_NONE)

    def is_only_local(self, permission: str) -> bool:
        """True si el permiso existe pero solo es local (nivel 1)."""
        return self.permission_level(permission) == LEVEL_LOCAL

    def has_non_local(self, permission: str) -> bool:
        """True si el permiso tiene algun componente no local (heredado o global)."""
        return self.permission_level(permission) >= LEVEL_INHERITED

    # ── Habilidades ────────────────────────────────────────────────────────

    def can(self, ability: str) -> bool:
        """Consulta una habilidad por nombre (ej. can('can_toggle_status'))."""
        cached = self._abilities_cache.get(ability)
        if cached is not None:
            return cached

        value = self._compute_ability(ability)
        self._abilities_cache[ability] = value
        return value

    def to_dict(self) -> dict[str, bool]:
        """Devuelve todas las habilidades en forma de diccionario."""
        return {ability: self.can(ability) for ability in ABILITY_PERMISSION_MAP}

    # ── Gestion de roles ──────────────────────────────────────────────────

    def can_manage_roles(self) -> bool:
        """True si el usuario puede gestionar roles en esta unidad (local o any)."""
        return self.can("can_members_manage_roles") or self.can("can_members_manage_roles_any")

    def manageable_role_min_level(self, my_role_level: int | None) -> int | None:
        """
        Devuelve el nivel minimo (0..N) de rol que puede gestionar
        el usuario en esta unidad.

        - Si NO tiene habilidad de gestion de roles -> None.
        - Si tiene can_members_manage_roles_any -> 0 (sin limite).
        - Si solo tiene can_members_manage_roles:
            - Limitado por su propio role.level en la unidad.
            - Si my_role_level es None -> None (no puede gestionar).

        Escala invertida: 0 = rol mas importante.
        """
        if not self.can_manage_roles():
            return None

        # Modo "any": puede gestionar cualquier rol
        if self.can("can_members_manage_roles_any"):
            return 0

        if not self.can("can_members_manage_roles"):
            return None

        # Sin nivel de rol conocido -> no puede gestionar
        if my_role_level is None:
            return None

        return my_role_level

    def can_manage_role_level(self, role_level: int, my_role_level: int | None) -> bool:
        """
        True si el usuario puede gestionar un rol cuyo level es *role_level*.

        Escala invertida: solo puede gestionar roles con level >= min gestionable.
        """
        min_level = self.manageable_role_min_level(my_role_level)
        if min_level is None:
            return False
        return role_level >= min_level

    # ── Requisitos de habilidades ──────────────────────────────────────────

    def ability_requirements(self) -> dict[str, dict[str, str | int]]:
        """Devuelve el mapa de requisitos: habilidad -> {permission, min_level}."""
        return {
            ability: {"permission": perm, "min_level": min_level}
            for ability, (perm, min_level) in ABILITY_PERMISSION_MAP.items()
        }

    def get_permissions(self) -> dict[str, int]:
        """Devuelve los niveles de permiso efectivos."""
        return dict(self._permission_levels)

    # ── Internos ───────────────────────────────────────────────────────────

    def _has_permission(self, permission: str, min_level: int) -> bool:
        """True si el permiso alcanza al menos el nivel indicado."""
        return self.permission_level(permission) >= min_level

    def _compute_ability(self, ability: str) -> bool:
        """Logica interna para una habilidad concreta."""
        entry = ABILITY_PERMISSION_MAP.get(ability)
        if entry is not None:
            perm, min_level = entry
            return self._has_permission(perm, min_level)
        # Habilidad no reconocida
        return False
