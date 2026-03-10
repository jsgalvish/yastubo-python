"""
Controlador de zonas geográficas (admin).
Equivale a ZoneController.php en Laravel.

Endpoints:
  GET    /admin/zones                              → index
  POST   /admin/zones                              → store
  GET    /admin/zones/{id}                         → show
  PUT    /admin/zones/{id}                         → update
  PUT    /admin/zones/{id}/toggle-active           → toggleActive
  GET    /admin/zones/{id}/countries               → countries (zonas de países)
  GET    /admin/zones/{id}/countries/available     → availableCountries
  POST   /admin/zones/{id}/countries/{country_id} → attachCountry
  DELETE /admin/zones/{id}/countries/{country_id} → detachCountry

Sin permiso explícito: solo requiere autenticación admin (get_admin_user).
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.http.middleware.auth import get_admin_user
from app.http.requests.admin.geo_request import (
    CountryAvailableOut,
    CountryForZoneOut,
    StoreZoneRequest,
    UpdateZoneRequest,
    ZoneOut,
)
from app.models.country import Country
from app.models.zone import Zone, country_zone
from config.continents import CONTINENTS

router = APIRouter(prefix="/admin/zones", tags=["admin:zones"])


def _build_country_for_zone(country: Country) -> CountryForZoneOut:
    data = CountryForZoneOut.model_validate(country)
    data.continent_label = CONTINENTS.get(country.continent_code, country.continent_code)
    return data


def _build_zone_out(zone: Zone) -> ZoneOut:
    """Construye ZoneOut con países y contador."""
    countries_out = [_build_country_for_zone(c) for c in zone.countries]
    return ZoneOut(
        id=zone.id,
        name=zone.name,
        description=zone.description,
        is_active=zone.is_active,
        countries=countries_out,
        countries_count=len(countries_out),
    )


async def _get_zone_with_countries(zone_id: int, db: AsyncSession) -> Zone:
    """Carga una zona con sus países (eager load). 404 si no existe."""
    result = await db.execute(
        select(Zone)
        .options(selectinload(Zone.countries))
        .where(Zone.id == zone_id)
    )
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada.")
    return zone


# ─────────────────────────── Endpoints ───────────────────────────────────────

@router.get("", response_model=list[ZoneOut])
async def index(
    _actor=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista todas las zonas con sus países."""
    result = await db.execute(
        select(Zone)
        .options(selectinload(Zone.countries))
        .order_by(Zone.id)
    )
    zones = list(result.scalars().all())
    return [_build_zone_out(z) for z in zones]


@router.post("", response_model=ZoneOut, status_code=201)
async def store(
    body: StoreZoneRequest,
    _actor=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Crea una nueva zona."""
    zone = Zone()
    zone.name = body.name
    zone.description = body.description
    zone.is_active = True

    db.add(zone)
    await db.commit()
    await db.refresh(zone)

    # Recargar con países (vacía en creación)
    zone = await _get_zone_with_countries(zone.id, db)
    return _build_zone_out(zone)


@router.get("/{zone_id}", response_model=ZoneOut)
async def show(
    zone_id: int,
    _actor=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna una zona por ID."""
    zone = await _get_zone_with_countries(zone_id, db)
    return _build_zone_out(zone)


@router.put("/{zone_id}", response_model=ZoneOut)
async def update(
    zone_id: int,
    body: UpdateZoneRequest,
    _actor=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza una zona (partial update con model_fields_set)."""
    zone = await _get_zone_with_countries(zone_id, db)

    if "name" in body.model_fields_set and body.name is not None:
        zone.name = body.name

    if "description" in body.model_fields_set:
        zone.description = body.description

    await db.commit()
    await db.refresh(zone)

    zone = await _get_zone_with_countries(zone_id, db)
    return _build_zone_out(zone)


@router.put("/{zone_id}/toggle-active", response_model=ZoneOut)
async def toggle_active(
    zone_id: int,
    _actor=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Activa o desactiva una zona."""
    zone = await _get_zone_with_countries(zone_id, db)
    zone.is_active = not zone.is_active
    await db.commit()
    await db.refresh(zone)

    zone = await _get_zone_with_countries(zone_id, db)
    return _build_zone_out(zone)


@router.get("/{zone_id}/countries", response_model=list[CountryForZoneOut])
async def zone_countries(
    zone_id: int,
    _actor=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista los países de una zona."""
    zone = await _get_zone_with_countries(zone_id, db)
    return [_build_country_for_zone(c) for c in zone.countries]


@router.get("/{zone_id}/countries/available", response_model=list[CountryAvailableOut])
async def available_countries(
    zone_id: int,
    _actor=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna todos los países con la bandera 'attached' indicando
    si ya pertenecen a la zona. Equivale a availableCountries() en PHP.
    """
    zone = await _get_zone_with_countries(zone_id, db)
    attached_ids = {c.id for c in zone.countries}

    all_result = await db.execute(select(Country).order_by(Country.id))
    all_countries = list(all_result.scalars().all())

    out = []
    for country in all_countries:
        item = CountryAvailableOut.model_validate(country)
        item.continent_label = CONTINENTS.get(country.continent_code, country.continent_code)
        item.attached = country.id in attached_ids
        out.append(item)

    return out


@router.post("/{zone_id}/countries/{country_id}", status_code=200)
async def attach_country(
    zone_id: int,
    country_id: int,
    _actor=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Asocia un país a una zona (idempotente, equivale a syncWithoutDetaching).
    """
    zone = await _get_zone_with_countries(zone_id, db)

    country_result = await db.execute(select(Country).where(Country.id == country_id))
    country = country_result.scalar_one_or_none()
    if country is None:
        raise HTTPException(status_code=404, detail="País no encontrado.")

    # Idempotente: insertar solo si no existe
    already = await db.execute(
        select(country_zone).where(
            country_zone.c.zone_id == zone_id,
            country_zone.c.country_id == country_id,
        )
    )
    if already.first() is None:
        await db.execute(
            country_zone.insert().values(zone_id=zone_id, country_id=country_id)
        )
        await db.commit()

    return {"message": "País asociado correctamente."}


@router.delete("/{zone_id}/countries/{country_id}", status_code=200)
async def detach_country(
    zone_id: int,
    country_id: int,
    _actor=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Desasocia un país de una zona."""
    # Verificar que la zona existe
    zone_result = await db.execute(select(Zone).where(Zone.id == zone_id))
    if zone_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada.")

    await db.execute(
        delete(country_zone).where(
            country_zone.c.zone_id == zone_id,
            country_zone.c.country_id == country_id,
        )
    )
    await db.commit()

    return {"message": "País desasociado correctamente."}
