"""
Controlador de países (admin).
Equivale a CountryController.php en Laravel.

Endpoints:
  GET    /admin/countries                    → index
  POST   /admin/countries                    → store
  GET    /admin/countries/{id}               → show
  PUT    /admin/countries/{id}               → update
  PUT    /admin/countries/{id}/toggle-active → toggleActive

Permiso requerido: admin.countries.manage
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_db
from common.middleware.permission import require_permission
from common.models.country import Country
from common.models.user import User
from config.continents import CONTINENTS

from ..requests.geo_request import (
    StoreCountryRequest,
    UpdateCountryRequest,
)

router = APIRouter(prefix="/admin/countries", tags=["admin:countries"])

_PERMISSION = "admin.countries.manage"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _transform_country(country: Country) -> dict:
    """
    Serializa un país para el frontend.
    Equivale a transformCountry() en PHP.
    """
    name_data: dict = {"es": None, "en": None}
    if country.name:
        try:
            parsed = json.loads(country.name) if isinstance(country.name, str) else country.name
            if isinstance(parsed, dict):
                name_data = {**name_data, **parsed}
        except Exception:
            name_data = {"es": country.name, "en": country.name}

    return {
        "id": country.id,
        "name": name_data,
        "iso2": country.iso2,
        "iso3": country.iso3,
        "continent_code": country.continent_code,
        "continent_label": CONTINENTS.get(country.continent_code, country.continent_code),
        "phone_code": country.phone_code,
        "is_active": bool(country.is_active),
    }


async def _get_country_or_404(db: AsyncSession, country_id: int) -> Country:
    result = await db.execute(select(Country).where(Country.id == country_id))
    country = result.scalar_one_or_none()
    if country is None:
        raise HTTPException(status_code=404, detail="País no encontrado.")
    return country


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("")
async def index(
    search: str = Query("", alias="search"),
    continent: str | None = Query(None, alias="continent"),
    status: str = Query("active", alias="status"),
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista países con filtros opcionales.
    Devuelve JSON con {countries, filters, continents}.
    """
    query = select(Country)

    search = search.strip()
    if search:
        like = f"%{search}%"
        query = query.where(
            or_(
                Country.name.like(like),
                Country.phone_code.like(like),
                Country.iso2.like(like),
                Country.iso3.like(like),
            )
        )

    if continent:
        query = query.where(Country.continent_code == continent)

    if status == "active":
        query = query.where(Country.is_active.is_(True))
    elif status == "inactive":
        query = query.where(Country.is_active.is_(False))

    query = query.order_by(Country.name)
    result = await db.execute(query)
    countries = list(result.scalars().all())

    return {
        "countries": [_transform_country(c) for c in countries],
        "filters": {"search": search, "continent": continent, "status": status},
        "continents": CONTINENTS,
    }


@router.post("", status_code=201)
async def store(
    body: StoreCountryRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Crea un nuevo país."""
    # Unicidad iso2
    existing = await db.execute(select(Country).where(Country.iso2 == body.iso2))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="El código ISO2 ya existe.")

    # Unicidad iso3
    existing = await db.execute(select(Country).where(Country.iso3 == body.iso3))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="El código ISO3 ya existe.")

    country = Country()
    country.name = json.dumps({"es": body.name.es, "en": body.name.en})
    country.iso2 = body.iso2
    country.iso3 = body.iso3
    country.continent_code = body.continent_code
    country.phone_code = body.phone_code
    country.is_active = True

    db.add(country)
    await db.commit()
    await db.refresh(country)

    return {"message": "País creado correctamente.", "data": _transform_country(country)}


@router.get("/{country_id}")
async def show(
    country_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Retorna un país por ID."""
    country = await _get_country_or_404(db, country_id)
    return {"data": _transform_country(country)}


@router.put("/{country_id}")
async def update(
    country_id: int,
    body: UpdateCountryRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza un país."""
    country = await _get_country_or_404(db, country_id)

    # Unicidad iso2 (excluyendo el propio país)
    existing = await db.execute(
        select(Country).where(Country.iso2 == body.iso2, Country.id != country_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="El código ISO2 ya existe.")

    # Unicidad iso3
    existing = await db.execute(
        select(Country).where(Country.iso3 == body.iso3, Country.id != country_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="El código ISO3 ya existe.")

    country.name = json.dumps({"es": body.name.es, "en": body.name.en})
    country.iso2 = body.iso2
    country.iso3 = body.iso3
    country.continent_code = body.continent_code
    country.phone_code = body.phone_code

    await db.commit()
    await db.refresh(country)

    return {"message": "País actualizado correctamente.", "data": _transform_country(country)}


@router.put("/{country_id}/toggle-active")
async def toggle_active(
    country_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Activa o desactiva un país."""
    country = await _get_country_or_404(db, country_id)

    country.is_active = not country.is_active
    await db.commit()
    await db.refresh(country)

    msg = "País activado correctamente." if country.is_active else "País desactivado correctamente."
    return {"message": msg, "data": _transform_country(country)}
