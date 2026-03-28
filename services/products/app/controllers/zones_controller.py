"""
Controlador de zonas geográficas (admin).
Equivale a ZoneController.php en Laravel.

Endpoints:
  GET    /admin/zones                              → index
  POST   /admin/zones                              → store
  GET    /admin/zones/{id}                         → show
  PUT    /admin/zones/{id}                         → update
  PUT    /admin/zones/{id}/toggle-active           → toggleActive
  GET    /admin/zones/{id}/countries               → countries
  GET    /admin/zones/{id}/countries/available     → availableCountries
  POST   /admin/zones/{id}/countries/{country_id}  → attachCountry
  DELETE /admin/zones/{id}/countries/{country_id}  → detachCountry

Sin permiso explícito: solo requiere autenticación admin (get_admin_user).
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.database import get_db
from common.models.user import User
from common.middleware.auth import get_admin_user
from app.requests.geo_request import (
    CountryAvailableOut,
    CountryForZoneOut,
    StoreZoneRequest,
    UpdateZoneRequest,
    ZoneOut,
    ZoneSimpleOut,
)
from common.models.country import Country
from common.models.zone import Zone, country_zone
from config.continents import CONTINENTS

router = APIRouter(prefix="/admin/zones", tags=["admin:zones"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _transform_country_for_zone(c: Country) -> dict:
    """Serializa un país en el contexto de zona. Equivale a transformCountryForZone() de PHP."""
    name_data: dict = {"es": None, "en": None}
    if c.name:
        try:
            parsed = json.loads(c.name) if isinstance(c.name, str) else c.name
            if isinstance(parsed, dict):
                name_data = {**name_data, **parsed}
        except Exception:
            name_data = {"es": c.name, "en": c.name}

    return {
        "id": c.id,
        "name": name_data,
        "continent_code": c.continent_code,
        "continent_label": CONTINENTS.get(c.continent_code, c.continent_code),
        "phone_code": c.phone_code,
        "is_active": bool(c.is_active),
    }


def _transform_zone(z: Zone) -> dict:
    """Serializa una zona con sus países. Equivale a transformZone() de PHP."""
    countries = sorted(z.countries, key=lambda c: c.name or "")
    countries_out = [_transform_country_for_zone(c) for c in countries]
    return {
        "id": z.id,
        "name": z.name,
        "description": z.description,
        "is_active": bool(z.is_active),
        "countries": countries_out,
        "countries_count": len(countries_out),
    }


async def _load_zone_or_404(db: AsyncSession, zone_id: int) -> Zone:
    """Carga la zona con países (selectinload). 404 si no existe."""
    result = await db.execute(
        select(Zone).options(selectinload(Zone.countries)).where(Zone.id == zone_id)
    )
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada.")
    return zone


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("")
async def index(
    status: str = Query("active", alias="status"),
    _current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista zonas con sus países.
    Devuelve JSON con {zones, filters, continents}.
    """
    query = select(Zone).options(selectinload(Zone.countries))

    if status == "active":
        query = query.where(Zone.is_active.is_(True))
    elif status == "inactive":
        query = query.where(Zone.is_active.is_(False))

    query = query.order_by(Zone.name)
    result = await db.execute(query)
    zones = list(result.scalars().all())

    return {
        "zones": [_transform_zone(z) for z in zones],
        "filters": {"status": status},
        "continents": CONTINENTS,
    }


@router.post("", status_code=201)
async def store(
    body: StoreZoneRequest,
    _current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Crea una nueva zona (siempre activa)."""
    zone = Zone()
    zone.name = body.name
    zone.description = body.description
    zone.is_active = True

    db.add(zone)
    await db.commit()
    await db.refresh(zone)

    zone = await _load_zone_or_404(db, zone.id)
    return {"message": "Zona creada correctamente.", "data": _transform_zone(zone)}


@router.get("/{zone_id}")
async def show(
    zone_id: int,
    _current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna datos básicos de la zona (sin cargar países completos).
    Equivale a show() de PHP — devuelve solo name, description, is_active.
    """
    result = await db.execute(select(Zone).where(Zone.id == zone_id))
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada.")

    return {
        "data": {
            "id": zone.id,
            "name": zone.name,
            "description": zone.description,
            "is_active": bool(zone.is_active),
        }
    }


@router.put("/{zone_id}")
async def update(
    zone_id: int,
    body: UpdateZoneRequest,
    _current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza nombre y descripción de una zona."""
    zone = await _load_zone_or_404(db, zone_id)

    zone.name = body.name
    zone.description = body.description

    await db.commit()
    await db.refresh(zone)

    zone = await _load_zone_or_404(db, zone_id)
    return {"message": "Zona actualizada correctamente.", "data": _transform_zone(zone)}


@router.put("/{zone_id}/toggle-active")
async def toggle_active(
    zone_id: int,
    _current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Activa o desactiva una zona."""
    zone = await _load_zone_or_404(db, zone_id)

    zone.is_active = not zone.is_active
    await db.commit()
    await db.refresh(zone)

    zone = await _load_zone_or_404(db, zone_id)
    msg = "Zona activada correctamente." if zone.is_active else "Zona desactivada correctamente."
    return {"message": msg, "data": _transform_zone(zone)}


@router.get("/{zone_id}/countries")
async def zone_countries(
    zone_id: int,
    _current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Países actualmente asociados a la zona.
    Equivale a countries() de PHP.
    """
    zone = await _load_zone_or_404(db, zone_id)
    countries = sorted(zone.countries, key=lambda c: c.name or "")

    return {
        "zone_id": zone.id,
        "countries": [_transform_country_for_zone(c) for c in countries],
    }


@router.get("/{zone_id}/countries/available")
async def available_countries(
    zone_id: int,
    search: str = Query("", alias="search"),
    continent: str | None = Query(None, alias="continent"),
    status: str = Query("active", alias="status"),
    _current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista de países con bandera 'attached'.
    Soporta filtros search, continent, status.
    Equivale a availableCountries() de PHP.
    """
    zone = await _load_zone_or_404(db, zone_id)
    attached_ids = {c.id for c in zone.countries}

    query = select(Country)

    search = search.strip()
    if search:
        query = query.where(Country.name.like(f"%{search}%"))

    if continent:
        query = query.where(Country.continent_code == continent)

    if status == "active":
        query = query.where(Country.is_active.is_(True))
    elif status == "inactive":
        query = query.where(Country.is_active.is_(False))

    query = query.order_by(Country.name)
    result = await db.execute(query)
    all_countries = list(result.scalars().all())

    items = []
    for c in all_countries:
        data = _transform_country_for_zone(c)
        data["attached"] = c.id in attached_ids
        items.append(data)

    return {
        "zone_id": zone_id,
        "countries": items,
        "filters": {"search": search, "continent": continent, "status": status},
        "continents": CONTINENTS,
    }


async def _do_attach_country(zone_id: int, country_id: int, db: AsyncSession):
    """Lógica compartida para asociar un país a una zona."""
    zone_result = await db.execute(select(Zone).where(Zone.id == zone_id))
    if zone_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada.")

    country_result = await db.execute(select(Country).where(Country.id == country_id))
    if country_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="País no encontrado.")

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

    return {"message": "País añadido a la zona."}


@router.post("/{zone_id}/countries/{country_id}", status_code=200)
async def attach_country(
    zone_id: int,
    country_id: int,
    _current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Asocia un país a una zona (path param)."""
    return await _do_attach_country(zone_id, country_id, db)


@router.post("/{zone_id}/countries", status_code=200)
async def attach_country_body(
    zone_id: int,
    body: dict,
    _current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Asocia un país a una zona (body param — usado por frontend)."""
    cid = body.get("country_id")
    if not cid:
        raise HTTPException(status_code=422, detail="country_id es requerido.")
    return await _do_attach_country(zone_id, int(cid), db)


@router.delete("/{zone_id}/countries/{country_id}", status_code=200)
async def detach_country(
    zone_id: int,
    country_id: int,
    _current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Desasocia un país de una zona."""
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

    return {"message": "País quitado de la zona."}
