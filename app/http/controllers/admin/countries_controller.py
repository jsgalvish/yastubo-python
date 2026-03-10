"""
Controlador de países (admin).
Equivale a CountryController.php en Laravel.

Endpoints:
  GET    /admin/countries              → index
  POST   /admin/countries              → store
  GET    /admin/countries/{id}         → show
  PUT    /admin/countries/{id}         → update
  PUT    /admin/countries/{id}/toggle-active → toggleActive

Permiso requerido: admin.countries.manage
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.http.middleware.permission import require_permission
from app.http.requests.admin.geo_request import (
    CountryOut,
    StoreCountryRequest,
    UpdateCountryRequest,
)
from app.models.country import Country
from config.continents import CONTINENTS

router = APIRouter(prefix="/admin/countries", tags=["admin:countries"])

_PERMISSION = "admin.countries.manage"


def _build_country_out(country: Country) -> CountryOut:
    """Construye CountryOut agregando continent_label (equivale a transformCountry)."""
    data = CountryOut.model_validate(country)
    data.continent_label = CONTINENTS.get(country.continent_code, country.continent_code)
    return data


# ─────────────────────────── Endpoints ───────────────────────────────────────

@router.get("", response_model=list[CountryOut])
async def index(
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Lista todos los países ordenados por nombre."""
    result = await db.execute(select(Country).order_by(Country.id))
    countries = list(result.scalars().all())
    return [_build_country_out(c) for c in countries]


@router.post("", response_model=CountryOut, status_code=201)
async def store(
    body: StoreCountryRequest,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Crea un nuevo país."""
    # Validar unicidad iso2
    existing_iso2 = await db.execute(select(Country).where(Country.iso2 == body.iso2))
    if existing_iso2.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="El código ISO2 ya existe.")

    # Validar unicidad iso3
    existing_iso3 = await db.execute(select(Country).where(Country.iso3 == body.iso3))
    if existing_iso3.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="El código ISO3 ya existe.")

    # Validar continent_code
    if body.continent_code not in CONTINENTS:
        raise HTTPException(status_code=422, detail="Código de continente no válido.")

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

    return _build_country_out(country)


@router.get("/{country_id}", response_model=CountryOut)
async def show(
    country_id: int,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Retorna un país por ID."""
    result = await db.execute(select(Country).where(Country.id == country_id))
    country = result.scalar_one_or_none()
    if country is None:
        raise HTTPException(status_code=404, detail="País no encontrado.")
    return _build_country_out(country)


@router.put("/{country_id}", response_model=CountryOut)
async def update(
    country_id: int,
    body: UpdateCountryRequest,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza un país (partial update con model_fields_set)."""
    result = await db.execute(select(Country).where(Country.id == country_id))
    country = result.scalar_one_or_none()
    if country is None:
        raise HTTPException(status_code=404, detail="País no encontrado.")

    if "name" in body.model_fields_set and body.name is not None:
        country.name = json.dumps({"es": body.name.es, "en": body.name.en})

    if "iso2" in body.model_fields_set and body.iso2 is not None:
        existing = await db.execute(
            select(Country).where(Country.iso2 == body.iso2, Country.id != country_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=422, detail="El código ISO2 ya existe.")
        country.iso2 = body.iso2

    if "iso3" in body.model_fields_set and body.iso3 is not None:
        existing = await db.execute(
            select(Country).where(Country.iso3 == body.iso3, Country.id != country_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=422, detail="El código ISO3 ya existe.")
        country.iso3 = body.iso3

    if "continent_code" in body.model_fields_set and body.continent_code is not None:
        if body.continent_code not in CONTINENTS:
            raise HTTPException(status_code=422, detail="Código de continente no válido.")
        country.continent_code = body.continent_code

    if "phone_code" in body.model_fields_set:
        country.phone_code = body.phone_code

    await db.commit()
    await db.refresh(country)

    return _build_country_out(country)


@router.put("/{country_id}/toggle-active", response_model=CountryOut)
async def toggle_active(
    country_id: int,
    _actor=Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Activa o desactiva un país."""
    result = await db.execute(select(Country).where(Country.id == country_id))
    country = result.scalar_one_or_none()
    if country is None:
        raise HTTPException(status_code=404, detail="País no encontrado.")

    country.is_active = not country.is_active
    await db.commit()
    await db.refresh(country)

    return _build_country_out(country)
