"""
Controlador de países y países de repatriación por versión de plan (admin).
Equivale a PlanVersionCountryController.php + PlanVersionRepatriationCountryController.php.

Endpoints PlanVersionCountry:
  GET    /admin/products/{pid}/plans/{vid}/countries                   → index
  POST   /admin/products/{pid}/plans/{vid}/countries                   → store
  POST   /admin/products/{pid}/plans/{vid}/countries/attach-zone       → attachZone
  PATCH  /admin/products/{pid}/plans/{vid}/countries/{country_id}      → update
  DELETE /admin/products/{pid}/plans/{vid}/countries/{country_id}      → destroy
  POST   /admin/products/{pid}/plans/{vid}/countries/detach-by-zone    → detachByZone

Endpoints PlanVersionRepatriationCountry:
  GET    /admin/products/{pid}/plans/{vid}/repatriation-countries                   → index
  POST   /admin/products/{pid}/plans/{vid}/repatriation-countries                   → store
  POST   /admin/products/{pid}/plans/{vid}/repatriation-countries/attach-zone       → attachZone
  DELETE /admin/products/{pid}/plans/{vid}/repatriation-countries/{country_id}      → destroy
  POST   /admin/products/{pid}/plans/{vid}/repatriation-countries/detach-by-zone    → detachByZone

Permiso requerido: admin.products.manage
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.http.middleware.permission import require_permission
from app.http.requests.admin.plan_version_country_request import (
    AttachCountriesRequest,
    AttachZoneRequest,
    DetachByZoneRequest,
    UpdateCountryPriceRequest,
)
from app.models.country import Country
from app.models.plan_version import (
    PlanVersion,
    plan_version_countries,
    plan_version_repatriation_countries,
)
from app.models.product import Product
from app.models.user import User
from app.models.zone import Zone
from config.continents import CONTINENTS

# ─── Routers ────────────────────────────────────────────────────────────────

pv_country_router = APIRouter(
    prefix="/admin/products/{product_id}/plans/{version_id}/countries",
    tags=["admin:plan-version-countries"],
)

pv_repatriation_router = APIRouter(
    prefix="/admin/products/{product_id}/plans/{version_id}/repatriation-countries",
    tags=["admin:plan-version-repatriation-countries"],
)

_PERMISSION = "admin.products.manage"


# ─────────────────────────── Helpers ─────────────────────────────────────────


async def _get_product(product_id: int, db: AsyncSession) -> Product:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    return product


async def _get_version(product_id: int, version_id: int, db: AsyncSession) -> PlanVersion:
    result = await db.execute(
        select(PlanVersion).where(
            PlanVersion.id == version_id,
            PlanVersion.product_id == product_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="Versión de plan no encontrada.")
    return version


def _parse_name(country: Country) -> dict:
    """Parsea el campo name JSON → {es, en}."""
    name_data: dict = {"es": None, "en": None}
    if country.name:
        try:
            parsed = json.loads(country.name) if isinstance(country.name, str) else country.name
            if isinstance(parsed, dict):
                name_data = {**name_data, **parsed}
        except Exception:
            name_data = {"es": country.name, "en": country.name}
    return name_data


def _transform_country(country: Country) -> dict:
    """Serializa un país base (sin price ni attached)."""
    return {
        "id": country.id,
        "name": _parse_name(country),
        "iso2": country.iso2,
        "iso3": country.iso3,
        "continent_code": country.continent_code,
        "continent_label": CONTINENTS.get(country.continent_code, country.continent_code),
        "phone_code": country.phone_code,
        "is_active": bool(country.is_active),
    }


def _transform_plan_country(country: Country, price: float | None) -> dict:
    """País asociado a la versión con precio."""
    data = _transform_country(country)
    data["price"] = float(price) if price is not None else None
    return data


def _transform_modal_country(country: Country, attached: bool, price: float | None) -> dict:
    """País para el modal (con flag attached y precio)."""
    data = _transform_country(country)
    data["attached"] = attached
    data["price"] = float(price) if price is not None else None
    return data


def _transform_repatriation_country(country: Country) -> dict:
    """País de repatriación (sin precio)."""
    return _transform_country(country)


def _transform_repatriation_modal_country(country: Country, attached: bool) -> dict:
    """País para modal de repatriación (con flag attached)."""
    data = _transform_country(country)
    data["attached"] = attached
    return data


async def _get_zone_or_404(
    zone_id: int, db: AsyncSession, *, require_active: bool = False,
) -> Zone:
    stmt = select(Zone).where(Zone.id == zone_id)
    if require_active:
        stmt = stmt.where(Zone.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    zone = result.scalar_one_or_none()
    if zone is None:
        detail = "Zona no encontrada o inactiva." if require_active else "Zona no encontrada."
        raise HTTPException(status_code=404, detail=detail)
    return zone


async def _get_zone_country_ids(zone: Zone, db: AsyncSession) -> list[int]:
    """Retorna los IDs de países de una zona."""
    from app.models.zone import country_zone

    result = await db.execute(
        select(country_zone.c.country_id).where(country_zone.c.zone_id == zone.id)
    )
    return [row[0] for row in result.all()]


async def _get_zones_with_count(db: AsyncSession) -> list[dict]:
    """Retorna zonas activas con conteo de países."""
    from app.models.zone import country_zone

    stmt = (
        select(
            Zone.id,
            Zone.name,
            func.count(country_zone.c.country_id).label("countries_count"),
        )
        .outerjoin(country_zone, Zone.id == country_zone.c.zone_id)
        .where(Zone.is_active == True)  # noqa: E712
        .group_by(Zone.id, Zone.name)
        .order_by(Zone.name)
    )
    result = await db.execute(stmt)
    return [
        {"id": row.id, "name": row.name, "countries_count": int(row.countries_count)}
        for row in result.all()
    ]


# ═════════════════════════════════════════════════════════════════════════════
# PLAN VERSION COUNTRIES
# ═════════════════════════════════════════════════════════════════════════════


@pv_country_router.get("")
async def countries_index(
    product_id: int,
    version_id: int,
    search: str = Query("", alias="search"),
    continent: str | None = Query(None, alias="continent"),
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Listado de países de la versión y datos de apoyo (zonas, continentes)."""
    await _get_version(product_id, version_id, db)

    # Todos los países (con filtros)
    stmt = select(Country)
    search_term = search.strip()
    if search_term:
        term = search_term.lower()
        stmt = stmt.where(
            func.lower(Country.name).contains(term)
            | func.lower(Country.iso2).contains(term)
            | func.lower(Country.iso3).contains(term)
        )
    if continent:
        stmt = stmt.where(Country.continent_code == continent)
    stmt = stmt.order_by(Country.name)

    countries_result = await db.execute(stmt)
    all_countries_list = list(countries_result.scalars().all())

    # Países ya asociados (con precio del pivot)
    attached_stmt = (
        select(Country, plan_version_countries.c.price)
        .join(
            plan_version_countries,
            Country.id == plan_version_countries.c.country_id,
        )
        .where(plan_version_countries.c.plan_version_id == version_id)
    )
    attached_result = await db.execute(attached_stmt)
    attached_rows = attached_result.all()

    attached_map: dict[int, float | None] = {}
    for country, price in attached_rows:
        attached_map[country.id] = float(price) if price is not None else None

    # plan_countries: solo los asociados
    plan_countries = [
        _transform_plan_country(country, price)
        for country, price in attached_rows
    ]

    # countries: todos con flag attached + precio
    countries = [
        _transform_modal_country(
            c,
            c.id in attached_map,
            attached_map.get(c.id),
        )
        for c in all_countries_list
    ]

    zones = await _get_zones_with_count(db)

    return {
        "data": {
            "plan_countries": plan_countries,
            "countries": countries,
            "zones": zones,
            "continents": CONTINENTS,
        }
    }


@pv_country_router.post("")
async def countries_store(
    product_id: int,
    version_id: int,
    body: AttachCountriesRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Asocia uno o varios países a la versión (sin precio específico)."""
    await _get_version(product_id, version_id, db)

    ids = list({cid for cid in body.country_ids if cid and cid > 0})
    if not ids:
        raise HTTPException(status_code=422, detail="No se recibieron países válidos.")

    # Validar que existan
    result = await db.execute(select(Country).where(Country.id.in_(ids)))
    countries = list(result.scalars().all())
    if not countries:
        raise HTTPException(status_code=422, detail="No se encontraron países para asociar.")

    country_ids = [c.id for c in countries]

    # IDs ya asociados
    existing_result = await db.execute(
        select(plan_version_countries.c.country_id).where(
            plan_version_countries.c.plan_version_id == version_id,
            plan_version_countries.c.country_id.in_(country_ids),
        )
    )
    existing_ids = {row[0] for row in existing_result.all()}
    new_ids = [cid for cid in country_ids if cid not in existing_ids]

    if not new_ids:
        return {
            "message": "Los países seleccionados ya estaban asociados a la versión.",
            "data": {"countries": []},
        }

    # Insertar en pivot
    await db.execute(
        insert(plan_version_countries),
        [{"plan_version_id": version_id, "country_id": cid, "price": None} for cid in new_ids],
    )
    await db.commit()

    # Obtener los países recién asociados
    attached_result = await db.execute(select(Country).where(Country.id.in_(new_ids)))
    attached_countries = list(attached_result.scalars().all())

    if not attached_countries:
        raise HTTPException(
            status_code=422,
            detail="No se pudieron asociar los países seleccionados.",
        )

    result_list = [_transform_plan_country(c, None) for c in attached_countries]

    return {
        "toast": {
            "message": "Países añadidos correctamente a la versión.",
            "type": "success",
        },
        "data": {
            "countries": result_list,
        },
    }


@pv_country_router.post("/attach-zone")
async def countries_attach_zone(
    product_id: int,
    version_id: int,
    body: AttachZoneRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Asocia todos los países de una zona activa a la versión."""
    await _get_version(product_id, version_id, db)

    if body.zone_id <= 0:
        raise HTTPException(status_code=422, detail="Zona no válida.")

    zone = await _get_zone_or_404(body.zone_id, db, require_active=True)
    zone_country_ids = await _get_zone_country_ids(zone, db)

    if not zone_country_ids:
        raise HTTPException(
            status_code=422,
            detail="La zona seleccionada no tiene países asociados.",
        )

    # IDs ya asociados
    existing_result = await db.execute(
        select(plan_version_countries.c.country_id).where(
            plan_version_countries.c.plan_version_id == version_id,
            plan_version_countries.c.country_id.in_(zone_country_ids),
        )
    )
    already_attached = {row[0] for row in existing_result.all()}
    attach_ids = [cid for cid in zone_country_ids if cid not in already_attached]

    if not attach_ids:
        return {
            "message": "Todos los países de la zona ya están asociados a la versión.",
            "data": {"countries": []},
        }

    await db.execute(
        insert(plan_version_countries),
        [{"plan_version_id": version_id, "country_id": cid, "price": None} for cid in attach_ids],
    )
    await db.commit()

    countries_result = await db.execute(select(Country).where(Country.id.in_(attach_ids)))
    countries = list(countries_result.scalars().all())

    result_list = [_transform_plan_country(c, None) for c in countries]

    return {
        "toast": {
            "message": "Zona añadida correctamente a la versión.",
            "type": "success",
        },
        "data": {
            "countries": result_list,
        },
    }


@pv_country_router.patch("/{country_id}")
async def countries_update(
    product_id: int,
    version_id: int,
    country_id: int,
    body: UpdateCountryPriceRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Actualiza el precio específico de un país para la versión."""
    await _get_version(product_id, version_id, db)

    # Verificar que el país está asociado
    exists_result = await db.execute(
        select(plan_version_countries.c.country_id).where(
            plan_version_countries.c.plan_version_id == version_id,
            plan_version_countries.c.country_id == country_id,
        )
    )
    if exists_result.first() is None:
        raise HTTPException(status_code=404)

    price = body.price
    if price is not None and price < 0:
        raise HTTPException(
            status_code=422,
            detail="El precio debe ser un número positivo o vacío.",
        )

    # Actualizar precio en pivot
    await db.execute(
        plan_version_countries.update()
        .where(
            plan_version_countries.c.plan_version_id == version_id,
            plan_version_countries.c.country_id == country_id,
        )
        .values(price=price)
    )
    await db.commit()

    # Obtener el país
    country_result = await db.execute(select(Country).where(Country.id == country_id))
    country = country_result.scalar_one()

    data = _transform_plan_country(country, price)

    return {
        "toast": {
            "message": "Precio por país actualizado correctamente.",
            "type": "success",
        },
        "data": data,
    }


@pv_country_router.delete("/{country_id}")
async def countries_destroy(
    product_id: int,
    version_id: int,
    country_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Desasocia un país concreto de la versión."""
    await _get_version(product_id, version_id, db)

    # Verificar que el país está asociado
    exists_result = await db.execute(
        select(plan_version_countries.c.country_id).where(
            plan_version_countries.c.plan_version_id == version_id,
            plan_version_countries.c.country_id == country_id,
        )
    )
    if exists_result.first() is None:
        return {
            "message": "El país no está asociado a esta versión.",
            "data": {"countries": []},
        }

    await db.execute(
        sa_delete(plan_version_countries).where(
            plan_version_countries.c.plan_version_id == version_id,
            plan_version_countries.c.country_id == country_id,
        )
    )
    await db.commit()

    country_result = await db.execute(select(Country).where(Country.id == country_id))
    country = country_result.scalar_one()

    data = _transform_plan_country(country, None)

    return {
        "toast": {
            "message": "País quitado correctamente de la versión.",
            "type": "success",
        },
        "data": {
            "countries": [data],
        },
    }


@pv_country_router.post("/detach-by-zone")
async def countries_detach_by_zone(
    product_id: int,
    version_id: int,
    body: DetachByZoneRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Desasocia todos los países de una zona de la versión."""
    await _get_version(product_id, version_id, db)

    if body.zone_id <= 0:
        raise HTTPException(status_code=422, detail="Zona no válida.")

    zone = await _get_zone_or_404(body.zone_id, db)
    zone_country_ids = await _get_zone_country_ids(zone, db)

    if not zone_country_ids:
        raise HTTPException(
            status_code=422,
            detail="La zona seleccionada no tiene países asociados.",
        )

    # IDs efectivamente asociados
    attached_result = await db.execute(
        select(plan_version_countries.c.country_id).where(
            plan_version_countries.c.plan_version_id == version_id,
            plan_version_countries.c.country_id.in_(zone_country_ids),
        )
    )
    attached_ids = [row[0] for row in attached_result.all()]

    if not attached_ids:
        return {
            "message": "Ninguno de los países de la zona está asociado a esta versión.",
            "data": {"countries": []},
        }

    await db.execute(
        sa_delete(plan_version_countries).where(
            plan_version_countries.c.plan_version_id == version_id,
            plan_version_countries.c.country_id.in_(attached_ids),
        )
    )
    await db.commit()

    countries_result = await db.execute(select(Country).where(Country.id.in_(attached_ids)))
    countries = list(countries_result.scalars().all())

    result_list = [_transform_plan_country(c, None) for c in countries]

    return {
        "toast": {
            "message": "Países de la zona quitados correctamente de la versión.",
            "type": "success",
        },
        "data": {
            "countries": result_list,
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# PLAN VERSION REPATRIATION COUNTRIES
# ═════════════════════════════════════════════════════════════════════════════


@pv_repatriation_router.get("")
async def repatriation_index(
    product_id: int,
    version_id: int,
    search: str = Query("", alias="search"),
    continent: str | None = Query(None, alias="continent"),
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Listado de países de repatriación de la versión."""
    await _get_version(product_id, version_id, db)

    # Todos los países (con filtros)
    stmt = select(Country)
    search_term = search.strip()
    if search_term:
        term = search_term.lower()
        stmt = stmt.where(
            func.lower(Country.name).contains(term)
            | func.lower(Country.iso2).contains(term)
            | func.lower(Country.iso3).contains(term)
        )
    if continent:
        stmt = stmt.where(Country.continent_code == continent)
    stmt = stmt.order_by(Country.name)

    countries_result = await db.execute(stmt)
    all_countries_list = list(countries_result.scalars().all())

    # Países de repatriación ya asociados
    attached_stmt = (
        select(Country)
        .join(
            plan_version_repatriation_countries,
            Country.id == plan_version_repatriation_countries.c.country_id,
        )
        .where(plan_version_repatriation_countries.c.plan_version_id == version_id)
    )
    attached_result = await db.execute(attached_stmt)
    attached_countries = list(attached_result.scalars().all())
    attached_ids = {c.id for c in attached_countries}

    plan_countries = [_transform_repatriation_country(c) for c in attached_countries]

    countries = [
        _transform_repatriation_modal_country(c, c.id in attached_ids)
        for c in all_countries_list
    ]

    zones = await _get_zones_with_count(db)

    return {
        "data": {
            "plan_countries": plan_countries,
            "countries": countries,
            "zones": zones,
            "continents": CONTINENTS,
        }
    }


@pv_repatriation_router.post("")
async def repatriation_store(
    product_id: int,
    version_id: int,
    body: AttachCountriesRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Asocia países como permitidos para repatriación."""
    await _get_version(product_id, version_id, db)

    ids = list({cid for cid in body.country_ids if cid and cid > 0})
    if not ids:
        raise HTTPException(status_code=422, detail="No se recibieron países válidos.")

    result = await db.execute(select(Country).where(Country.id.in_(ids)))
    countries = list(result.scalars().all())
    if not countries:
        raise HTTPException(status_code=422, detail="No se encontraron países para asociar.")

    country_ids = [c.id for c in countries]

    existing_result = await db.execute(
        select(plan_version_repatriation_countries.c.country_id).where(
            plan_version_repatriation_countries.c.plan_version_id == version_id,
            plan_version_repatriation_countries.c.country_id.in_(country_ids),
        )
    )
    existing_ids = {row[0] for row in existing_result.all()}
    new_ids = [cid for cid in country_ids if cid not in existing_ids]

    if not new_ids:
        return {
            "message": "Los países seleccionados ya estaban asociados como permitidos para repatriación.",
            "data": {"countries": []},
        }

    await db.execute(
        insert(plan_version_repatriation_countries),
        [{"plan_version_id": version_id, "country_id": cid} for cid in new_ids],
    )
    await db.commit()

    attached_result = await db.execute(select(Country).where(Country.id.in_(new_ids)))
    attached_countries = list(attached_result.scalars().all())

    if not attached_countries:
        raise HTTPException(
            status_code=422,
            detail="No se pudieron asociar los países seleccionados.",
        )

    result_list = [_transform_repatriation_country(c) for c in attached_countries]

    return {
        "toast": {
            "message": "Países añadidos correctamente como permitidos para repatriación.",
            "type": "success",
        },
        "data": {
            "countries": result_list,
        },
    }


@pv_repatriation_router.post("/attach-zone")
async def repatriation_attach_zone(
    product_id: int,
    version_id: int,
    body: AttachZoneRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Asocia todos los países de una zona activa como permitidos para repatriación."""
    await _get_version(product_id, version_id, db)

    if body.zone_id <= 0:
        raise HTTPException(status_code=422, detail="Zona no válida.")

    zone = await _get_zone_or_404(body.zone_id, db, require_active=True)
    zone_country_ids = await _get_zone_country_ids(zone, db)

    if not zone_country_ids:
        raise HTTPException(
            status_code=422,
            detail="La zona seleccionada no tiene países asociados.",
        )

    existing_result = await db.execute(
        select(plan_version_repatriation_countries.c.country_id).where(
            plan_version_repatriation_countries.c.plan_version_id == version_id,
            plan_version_repatriation_countries.c.country_id.in_(zone_country_ids),
        )
    )
    already_attached = {row[0] for row in existing_result.all()}
    attach_ids = [cid for cid in zone_country_ids if cid not in already_attached]

    if not attach_ids:
        return {
            "message": "Todos los países de la zona ya están asociados como permitidos para repatriación en esta versión.",
            "data": {"countries": []},
        }

    await db.execute(
        insert(plan_version_repatriation_countries),
        [{"plan_version_id": version_id, "country_id": cid} for cid in attach_ids],
    )
    await db.commit()

    countries_result = await db.execute(select(Country).where(Country.id.in_(attach_ids)))
    countries = list(countries_result.scalars().all())

    result_list = [_transform_repatriation_country(c) for c in countries]

    return {
        "toast": {
            "message": "Zona añadida correctamente como permitida para repatriación.",
            "type": "success",
        },
        "data": {
            "countries": result_list,
        },
    }


@pv_repatriation_router.delete("/{country_id}")
async def repatriation_destroy(
    product_id: int,
    version_id: int,
    country_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Desasocia un país de los permitidos para repatriación."""
    await _get_version(product_id, version_id, db)

    exists_result = await db.execute(
        select(plan_version_repatriation_countries.c.country_id).where(
            plan_version_repatriation_countries.c.plan_version_id == version_id,
            plan_version_repatriation_countries.c.country_id == country_id,
        )
    )
    if exists_result.first() is None:
        return {
            "message": "El país no está asociado como permitido para repatriación en esta versión.",
            "data": {"countries": []},
        }

    await db.execute(
        sa_delete(plan_version_repatriation_countries).where(
            plan_version_repatriation_countries.c.plan_version_id == version_id,
            plan_version_repatriation_countries.c.country_id == country_id,
        )
    )
    await db.commit()

    country_result = await db.execute(select(Country).where(Country.id == country_id))
    country = country_result.scalar_one()

    data = _transform_repatriation_country(country)

    return {
        "toast": {
            "message": "País quitado correctamente de los permitidos para repatriación.",
            "type": "success",
        },
        "data": {
            "countries": [data],
        },
    }


@pv_repatriation_router.post("/detach-by-zone")
async def repatriation_detach_by_zone(
    product_id: int,
    version_id: int,
    body: DetachByZoneRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Desasocia todos los países de una zona de los permitidos para repatriación."""
    await _get_version(product_id, version_id, db)

    if body.zone_id <= 0:
        raise HTTPException(status_code=422, detail="Zona no válida.")

    zone = await _get_zone_or_404(body.zone_id, db)
    zone_country_ids = await _get_zone_country_ids(zone, db)

    if not zone_country_ids:
        raise HTTPException(
            status_code=422,
            detail="La zona seleccionada no tiene países asociados.",
        )

    attached_result = await db.execute(
        select(plan_version_repatriation_countries.c.country_id).where(
            plan_version_repatriation_countries.c.plan_version_id == version_id,
            plan_version_repatriation_countries.c.country_id.in_(zone_country_ids),
        )
    )
    attached_ids = [row[0] for row in attached_result.all()]

    if not attached_ids:
        return {
            "message": "Ninguno de los países de la zona está asociado como permitido para repatriación en esta versión.",
            "data": {"countries": []},
        }

    await db.execute(
        sa_delete(plan_version_repatriation_countries).where(
            plan_version_repatriation_countries.c.plan_version_id == version_id,
            plan_version_repatriation_countries.c.country_id.in_(attached_ids),
        )
    )
    await db.commit()

    countries_result = await db.execute(select(Country).where(Country.id.in_(attached_ids)))
    countries = list(countries_result.scalars().all())

    result_list = [_transform_repatriation_country(c) for c in countries]

    return {
        "toast": {
            "message": "Países de la zona quitados correctamente de los permitidos para repatriación.",
            "type": "success",
        },
        "data": {
            "countries": result_list,
        },
    }
