"""
Servicio de dominio para Regalias.

Migrado de App\\Services\\RegaliasService.php (Laravel).

Concentra:
  - Tipos de origen permitidos segun configuracion APP_REGALIAS.
  - Creacion, actualizacion y eliminacion de Regalias.
  - Validacion de ciclos usuario-usuario (DFS).
  - Validacion de redundancias ciclicas en jerarquia de unidades.
"""
from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.business_unit import BusinessUnit
from app.models.regalia import Regalia
from app.models.user import User

# Tipos soportados por el backend.
_SUPPORTED_SOURCE_TYPES = {"user", "unit"}


class RegaliasService:
    """
    Equivale a App\\Services\\RegaliasService de PHP.

    Recibe una AsyncSession por request (inyectada via Depends).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Tipos de origen permitidos
    # ------------------------------------------------------------------

    def allowed_source_types(self) -> list[str]:
        """
        Tipos de origen permitidos segun APP_REGALIAS.

        - Si APP_REGALIAS viene vacio => [].
        - Si viene no-vacio pero no se obtiene ningun tipo => 500.
        - Si contiene algun tipo invalido/no soportado => 500.
        """
        raw: str = settings.app_regalias

        if not raw or not raw.strip():
            return []

        parts = [p.strip() for p in raw.split(",")]
        parts = [p for p in parts if p]

        if not parts:
            raise HTTPException(
                status_code=500,
                detail="APP_REGALIAS esta mal formateado (no se encontraron tipos de origen).",
            )

        normalized: list[str] = []
        for p in parts:
            lower = p.lower()

            if not re.match(r"^[a-z0-9_-]+$", lower):
                raise HTTPException(
                    status_code=500,
                    detail=f"APP_REGALIAS contiene un tipo de origen invalido: {p}",
                )

            if lower not in _SUPPORTED_SOURCE_TYPES:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"APP_REGALIAS contiene un tipo de origen no soportado "
                        f"por el backend: {p}"
                    ),
                )

            normalized.append(lower)

        if not normalized:
            raise HTTPException(
                status_code=500,
                detail="APP_REGALIAS no contiene tipos de origen soportados.",
            )

        # Eliminar duplicados manteniendo orden
        seen: set[str] = set()
        unique: list[str] = []
        for item in normalized:
            if item not in seen:
                seen.add(item)
                unique.append(item)

        return unique

    def regalias_sources(self) -> list[str]:
        """Lista de tipos de origen a exponer al front."""
        return self.allowed_source_types()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_regalia(
        self, beneficiary_id: int, source_type: str, source_id: int
    ) -> Regalia:
        """
        Crea una Regalia, incluyendo validaciones de:
          - existencia de origen
          - duplicados
          - ciclos usuario-usuario
          - redundancias ciclicas de unidades

        Lanza HTTPException 422 para errores de negocio.
        """
        db = self._db

        # Validar existencia del origen segun tipo
        if source_type == "user":
            result = await db.execute(
                select(User).where(User.id == source_id, User.realm == "admin")
            )
            if result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=422, detail="Usuario origen no encontrado."
                )

        elif source_type == "unit":
            result = await db.execute(
                select(BusinessUnit).where(BusinessUnit.id == source_id)
            )
            if result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=422,
                    detail="Unidad de negocio origen no encontrada.",
                )

        else:
            raise HTTPException(
                status_code=500,
                detail="Tipo de origen de regalia no soportado por el backend.",
            )

        # Evitar duplicados
        existing = await db.execute(
            select(Regalia).where(
                Regalia.beneficiary_user_id == beneficiary_id,
                Regalia.source_type == source_type,
                Regalia.source_id == source_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=422,
                detail="Ya existe una regalia para este beneficiario y origen.",
            )

        # Validar ciclos en relaciones usuario-usuario
        if source_type == "user" and await self._would_create_user_cycle(beneficiary_id, source_id):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "La relacion de regalias entre usuarios genera un "
                        "ciclo y no es valida."
                    ),
                )

        # Validar redundancias ciclicas en relaciones de unidades
        if source_type == "unit" and await self._would_create_unit_redundancy_cycle(
            beneficiary_id, source_id
        ):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "La unidad seleccionada genera una redundancia en la "
                        "jerarquia de unidades para este beneficiario y no es "
                        "valida."
                    ),
                )

        regalia = Regalia()
        regalia.beneficiary_user_id = beneficiary_id
        regalia.source_type = source_type
        regalia.source_id = source_id
        regalia.commission = 0

        db.add(regalia)
        await db.commit()
        await db.refresh(regalia)

        return regalia

    async def update_commission(
        self, regalia: Regalia, commission: float | None
    ) -> Regalia:
        """
        Actualiza el porcentaje de comision de una Regalia.
        Aplica clamp 0-100 antes de guardar.
        """
        if commission is None:
            regalia.commission = 0
        else:
            regalia.commission = float(commission)

        # Clamp por seguridad
        if regalia.commission < 0:
            regalia.commission = 0
        elif regalia.commission > 100:
            regalia.commission = 100

        await self._db.commit()
        await self._db.refresh(regalia)

        return regalia

    async def delete_regalia(self, regalia: Regalia) -> dict:
        """
        Elimina una Regalia y devuelve el payload basico
        que se necesita para responder al front.
        """
        payload = {
            "id": regalia.id,
            "beneficiary_user_id": regalia.beneficiary_user_id,
            "source_type": regalia.source_type,
            "source_id": regalia.source_id,
        }

        await self._db.delete(regalia)
        await self._db.commit()

        return payload

    # ------------------------------------------------------------------
    # Deteccion de ciclos usuario-usuario (DFS)
    # ------------------------------------------------------------------

    async def _would_create_user_cycle(
        self, beneficiary_id: int, source_id: int
    ) -> bool:
        """
        Verifica si al crear una relacion de regalia usuario-usuario
        beneficiary_id -> source_id se generaria un ciclo en el grafo.

        El grafo esta definido por las aristas
        (beneficiary_user_id) -> (source_id) de todas las Regalia con
        source_type = 'user'.

        Agregar beneficiary_id -> source_id genera un ciclo si YA existe
        un camino desde source_id hasta beneficiary_id.
        """
        # Ciclo trivial: usuario que se apunta a si mismo
        if beneficiary_id == source_id:
            return True

        # Cargar todas las relaciones usuario-usuario existentes
        result = await self._db.execute(
            select(Regalia.beneficiary_user_id, Regalia.source_id).where(
                Regalia.source_type == "user"
            )
        )
        rows = result.all()

        # Construir lista de adyacencia: from -> {to1, to2, ...}
        adjacency: dict[int, set[int]] = {}
        for row in rows:
            from_id = int(row.beneficiary_user_id)
            to_id = int(row.source_id)
            if from_id not in adjacency:
                adjacency[from_id] = set()
            adjacency[from_id].add(to_id)

        # DFS desde source_id: si alcanzamos beneficiary_id, el nuevo
        # enlace cerraria un ciclo.
        stack = [source_id]
        visited: set[int] = {source_id}

        while stack:
            current = stack.pop()

            if current == beneficiary_id:
                return True

            neighbors = adjacency.get(current)
            if neighbors is None:
                continue

            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)

        return False

    # ------------------------------------------------------------------
    # Deteccion de redundancias ciclicas en jerarquia de unidades
    # ------------------------------------------------------------------

    async def _would_create_unit_redundancy_cycle(
        self, beneficiary_id: int, unit_id: int
    ) -> bool:
        """
        Verifica si al crear una regalia de unidad
        beneficiary_id -> unit_id (source_type = 'unit')
        se generaria una redundancia ciclica en la jerarquia de
        unidades para ese beneficiario.

        Reglas:
          1. Para cada unidad ya asignada Ue, subir por ancestor_chain()
             y verificar que la unidad candidata (unit_id) NO este en
             esa cadena.
          2. Tomar la unidad candidata y subir por ancestor_chain() y
             verificar que NINGUNA de las unidades ya asignadas este en
             esa cadena.
        """
        db = self._db

        # Todas las unidades ya asignadas (origen unit) para este beneficiario
        result = await db.execute(
            select(Regalia.source_id).where(
                Regalia.beneficiary_user_id == beneficiary_id,
                Regalia.source_type == "unit",
            )
        )
        existing_unit_ids = list(
            {int(row[0]) for row in result.all() if row[0] is not None}
        )

        if not existing_unit_ids:
            return False

        # Si la nueva unidad ya esta en la lista, es redundancia
        if unit_id in existing_unit_ids:
            return True

        # Cargar todas las unidades relevantes (existentes + candidata)
        # con relacion parent para poder recorrer ancestor_chain
        all_ids = list({*existing_unit_ids, unit_id})
        units_result = await db.execute(
            select(BusinessUnit)
            .options(selectinload(BusinessUnit.parent))
            .where(BusinessUnit.id.in_(all_ids))
        )
        units_map: dict[int, BusinessUnit] = {
            bu.id: bu for bu in units_result.scalars().all()
        }

        candidate = units_map.get(unit_id)
        if candidate is None:
            return False

        # Cadena de ancestros de la unidad candidata
        candidate_chain_ids = {bu.id for bu in candidate.ancestor_chain()}

        # Regla 1: para cada unidad ya asignada, verificar que la candidata
        # no este en su cadena de ancestros
        for existing_id in existing_unit_ids:
            existing = units_map.get(existing_id)
            if existing is None:
                continue

            chain_ids = {bu.id for bu in existing.ancestor_chain()}
            if unit_id in chain_ids:
                return True

        # Regla 2: verificar que ninguna unidad ya asignada este en la
        # cadena de ancestros de la candidata
        return any(existing_id in candidate_chain_ids for existing_id in existing_unit_ids)
