"""
Controlador del catálogo de coberturas (admin).
Equivale a CoverageCatalogController.php + PlanVersionCoverageController.php.

Endpoints Catálogo:
  GET    /admin/coverages                                    → index
  POST   /admin/coverages/categories                         → storeCategory
  PUT    /admin/coverages/categories/{id}                    → updateCategory
  POST   /admin/coverages/categories/{id}/archive            → archiveCategory
  POST   /admin/coverages/categories/{id}/restore            → restoreCategory
  GET    /admin/coverages/categories/archived                → archivedCategories
  POST   /admin/coverages/categories/{id}/reorder            → reorderCoverages
  POST   /admin/coverages/items                              → storeCoverage
  PUT    /admin/coverages/items/{id}                         → updateCoverage
  POST   /admin/coverages/items/{id}/archive                 → archiveCoverage
  POST   /admin/coverages/items/{id}/restore                 → restoreCoverage
  DELETE /admin/coverages/items/{id}                         → destroyCoverage
  GET    /admin/coverages/items/{id}/usages                  → coverageUsages

Endpoints PlanVersionCoverage:
  GET    /admin/products/{pid}/plans/{vid}/coverages/available  → available
  POST   /admin/products/{pid}/plans/{vid}/coverages           → store
  DELETE /admin/products/{pid}/plans/{vid}/coverages/{cid}     → destroy
  POST   /admin/products/{pid}/plans/{vid}/coverages/reorder   → reorder
  PATCH  /admin/products/{pid}/plans/{vid}/coverages/{cid}     → updateValue

Permiso requerido: admin.coverages.manage / admin.products.manage
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.requests.coverage_request import (
    ArchivedCategoriesResponse,
    AvailableCategoryOut,
    AvailableCoverageItem,
    AvailableCoveragesResponse,
    CatalogIndexResponse,
    CategoryDataResponse,
    CategoryOut,
    CoverageDataResponse,
    CoverageOut,
    PlanVersionCoverageDataResponse,
    PlanVersionCoverageOut,
    ReorderCoveragesRequest,
    ReorderPVCoveragesRequest,
    StoreCategoryRequest,
    StoreCoverageRequest,
    StorePlanVersionCoverageRequest,
    UnitOut,
    UpdateCoverageRequest,
    UpdatePVCoverageValueRequest,
)
from common.database import get_db
from common.middleware.permission import require_permission
from common.models.coverage import Coverage
from common.models.coverage_category import CoverageCategory
from common.models.plan_version import PlanVersion
from common.models.plan_version_coverage import PlanVersionCoverage
from common.models.product import Product
from common.models.unit_of_measure import UnitOfMeasure
from common.models.user import User

# ─── Catálogo router ─────────────────────────────────────────────────────────

catalog_router = APIRouter(prefix="/admin/coverages", tags=["admin:coverages"])
_CATALOG_PERM = "admin.coverages.manage"

# ─── PlanVersion coverage router ─────────────────────────────────────────────

pv_cov_router = APIRouter(
    prefix="/admin/products/{product_id}/plans/{version_id}/coverages",
    tags=["admin:plan-version-coverages"],
)
_PV_PERM = "admin.products.manage"


# ─────────────────────────── Helpers ─────────────────────────────────────────


def _pj(val: str | None) -> dict | None:
    """Parse JSON field."""
    if val is None:
        return None
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, ValueError):
        return None


def _dj(data: dict | None) -> str | None:
    """Dump dict to JSON string."""
    if data is None:
        return None
    return json.dumps(data, ensure_ascii=False)


def _unit_out(u: UnitOfMeasure) -> UnitOut:
    return UnitOut(
        id=u.id,
        name=_pj(u.name),
        description=_pj(u.description),
        measure_type=u.measure_type,
        status=u.status,
    )


def _coverage_out(c: Coverage) -> CoverageOut:
    return CoverageOut(
        id=c.id,
        category_id=c.category_id,
        unit_id=c.unit_id,
        name=_pj(c.name),
        description=_pj(c.description),
        status=c.status,
        sort_order=c.sort_order,
        unit=_unit_out(c.unit) if c.unit else None,
    )


def _category_out(cat: CoverageCategory, include_coverages: bool = True) -> CategoryOut:
    covs = []
    if include_coverages and cat.coverages:
        covs = [_coverage_out(c) for c in cat.coverages if c.status == "active"]
    return CategoryOut(
        id=cat.id,
        name=_pj(cat.name),
        description=_pj(cat.description),
        status=cat.status,
        sort_order=cat.sort_order,
        coverages=covs,
    )


def _pv_coverage_out(pvc: PlanVersionCoverage) -> PlanVersionCoverageOut:
    cov = pvc.coverage
    unit = cov.unit if cov else None
    cat = cov.category if cov else None
    return PlanVersionCoverageOut(
        id=pvc.id,
        plan_version_id=pvc.plan_version_id,
        coverage_id=pvc.coverage_id,
        sort_order=pvc.sort_order,
        value_int=pvc.value_int,
        value_decimal=float(pvc.value_decimal) if pvc.value_decimal is not None else None,
        value_text=_pj(pvc.value_text),
        notes=_pj(pvc.notes),
        coverage_name=_pj(cov.name) if cov else None,
        coverage_description=_pj(cov.description) if cov else None,
        unit_name=_pj(unit.name) if unit else None,
        unit_measure_type=unit.measure_type if unit else None,
        category_id=cat.id if cat else None,
        category_name=_pj(cat.name) if cat else None,
    )


async def _get_product(pid: int, db: AsyncSession) -> Product:
    r = await db.execute(select(Product).where(Product.id == pid))
    p = r.scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    return p


async def _get_version(pid: int, vid: int, db: AsyncSession) -> PlanVersion:
    r = await db.execute(
        select(PlanVersion).where(PlanVersion.id == vid, PlanVersion.product_id == pid)
    )
    v = r.scalar_one_or_none()
    if v is None:
        raise HTTPException(status_code=404, detail="Versión de plan no encontrada.")
    return v


# ═════════════════════════════════════════════════════════════════════════════
# CATÁLOGO: Categorías
# ═════════════════════════════════════════════════════════════════════════════


@catalog_router.get("", response_model=CatalogIndexResponse)
async def catalog_index(
    _current_user: User = Depends(require_permission(_CATALOG_PERM)),
    db: AsyncSession = Depends(get_db),
) -> CatalogIndexResponse:
    """Lista categorías activas con coberturas + unidades de medida."""
    cats_r = await db.execute(
        select(CoverageCategory)
        .options(selectinload(CoverageCategory.coverages).selectinload(Coverage.unit))
        .where(CoverageCategory.status == "active")
        .order_by(CoverageCategory.sort_order)
    )
    categories = [_category_out(c) for c in cats_r.scalars().all()]

    units_r = await db.execute(
        select(UnitOfMeasure).where(UnitOfMeasure.status == "active").order_by(UnitOfMeasure.id)
    )
    units = [_unit_out(u) for u in units_r.scalars().all()]

    return CatalogIndexResponse(categories=categories, units=units)


@catalog_router.post("/categories", response_model=CategoryDataResponse, status_code=201)
async def store_category(
    body: StoreCategoryRequest,
    _current_user: User = Depends(require_permission(_CATALOG_PERM)),
    db: AsyncSession = Depends(get_db),
) -> CategoryDataResponse:
    """Crea una categoría de cobertura."""
    max_order = (
        await db.execute(select(func.coalesce(func.max(CoverageCategory.sort_order), 0)))
    ).scalar() or 0

    cat = CoverageCategory()
    cat.name = _dj(body.name.model_dump())
    cat.description = _dj(body.description.model_dump()) if body.description else None
    cat.status = "active"
    cat.sort_order = max_order + 1

    db.add(cat)
    await db.commit()
    await db.refresh(cat)

    return CategoryDataResponse(data=_category_out(cat, include_coverages=False))


@catalog_router.put("/categories/{category_id}", response_model=CategoryDataResponse)
async def update_category(
    category_id: int,
    body: StoreCategoryRequest,
    _current_user: User = Depends(require_permission(_CATALOG_PERM)),
    db: AsyncSession = Depends(get_db),
) -> CategoryDataResponse:
    """Actualiza una categoría."""
    r = await db.execute(select(CoverageCategory).where(CoverageCategory.id == category_id))
    cat = r.scalar_one_or_none()
    if cat is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    cat.name = _dj(body.name.model_dump())
    cat.description = _dj(body.description.model_dump()) if body.description else None

    await db.commit()
    await db.refresh(cat)

    return CategoryDataResponse(data=_category_out(cat, include_coverages=False))


@catalog_router.post("/categories/{category_id}/archive", response_model=dict)
async def archive_category(
    category_id: int,
    _current_user: User = Depends(require_permission(_CATALOG_PERM)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Archiva una categoría."""
    r = await db.execute(select(CoverageCategory).where(CoverageCategory.id == category_id))
    cat = r.scalar_one_or_none()
    if cat is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    cat.status = "archived"
    await db.commit()
    return {"message": "Categoría archivada correctamente."}


@catalog_router.post("/categories/{category_id}/restore", response_model=CategoryDataResponse)
async def restore_category(
    category_id: int,
    _current_user: User = Depends(require_permission(_CATALOG_PERM)),
    db: AsyncSession = Depends(get_db),
) -> CategoryDataResponse:
    """Restaura una categoría archivada."""
    r = await db.execute(
        select(CoverageCategory)
        .options(selectinload(CoverageCategory.coverages).selectinload(Coverage.unit))
        .where(CoverageCategory.id == category_id)
    )
    cat = r.scalar_one_or_none()
    if cat is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    cat.status = "active"
    await db.commit()
    await db.refresh(cat)

    return CategoryDataResponse(data=_category_out(cat))


@catalog_router.get("/categories/archived", response_model=ArchivedCategoriesResponse)
async def archived_categories(
    _current_user: User = Depends(require_permission(_CATALOG_PERM)),
    db: AsyncSession = Depends(get_db),
) -> ArchivedCategoriesResponse:
    """Lista categorías archivadas."""
    r = await db.execute(
        select(CoverageCategory)
        .where(CoverageCategory.status == "archived")
        .order_by(CoverageCategory.sort_order)
    )
    return ArchivedCategoriesResponse(
        data=[_category_out(c, include_coverages=False) for c in r.scalars().all()]
    )


@catalog_router.post("/categories/{category_id}/reorder", response_model=dict)
async def reorder_coverages(
    category_id: int,
    body: ReorderCoveragesRequest,
    _current_user: User = Depends(require_permission(_CATALOG_PERM)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reordena coberturas dentro de una categoría."""
    for item in body.items:
        r = await db.execute(
            select(Coverage).where(Coverage.id == item.id, Coverage.category_id == category_id)
        )
        cov = r.scalar_one_or_none()
        if cov:
            cov.sort_order = item.sort_order
    await db.commit()
    return {"message": "Orden actualizado correctamente."}


# ═════════════════════════════════════════════════════════════════════════════
# CATÁLOGO: Coverage items
# ═════════════════════════════════════════════════════════════════════════════


@catalog_router.post("/items", response_model=CoverageDataResponse, status_code=201)
async def store_coverage(
    body: StoreCoverageRequest,
    _current_user: User = Depends(require_permission(_CATALOG_PERM)),
    db: AsyncSession = Depends(get_db),
) -> CoverageDataResponse:
    """Crea una cobertura."""
    max_order = (
        await db.execute(
            select(func.coalesce(func.max(Coverage.sort_order), 0)).where(
                Coverage.category_id == body.category_id
            )
        )
    ).scalar() or 0

    cov = Coverage()
    cov.category_id = body.category_id
    cov.unit_id = body.unit_id
    cov.name = _dj(body.name.model_dump())
    cov.description = _dj(body.description.model_dump()) if body.description else None
    cov.status = "active"
    cov.sort_order = max_order + 1

    db.add(cov)
    await db.commit()

    # Reload with unit
    r = await db.execute(
        select(Coverage).options(selectinload(Coverage.unit)).where(Coverage.id == cov.id)
    )
    cov = r.scalar_one()

    return CoverageDataResponse(data=_coverage_out(cov))


@catalog_router.put("/items/{coverage_id}", response_model=CoverageDataResponse)
async def update_coverage(
    coverage_id: int,
    body: UpdateCoverageRequest,
    _current_user: User = Depends(require_permission(_CATALOG_PERM)),
    db: AsyncSession = Depends(get_db),
) -> CoverageDataResponse:
    """Actualiza una cobertura."""
    r = await db.execute(
        select(Coverage).options(selectinload(Coverage.unit)).where(Coverage.id == coverage_id)
    )
    cov = r.scalar_one_or_none()
    if cov is None:
        raise HTTPException(status_code=404, detail="Cobertura no encontrada.")

    fields = body.model_fields_set
    if "category_id" in fields:
        cov.category_id = body.category_id
    if "unit_id" in fields:
        cov.unit_id = body.unit_id
    if "name" in fields and body.name:
        cov.name = _dj(body.name.model_dump())
    if "description" in fields:
        cov.description = _dj(body.description.model_dump()) if body.description else None

    await db.commit()

    r = await db.execute(
        select(Coverage).options(selectinload(Coverage.unit)).where(Coverage.id == cov.id)
    )
    cov = r.scalar_one()

    return CoverageDataResponse(data=_coverage_out(cov))


@catalog_router.post("/items/{coverage_id}/archive", response_model=dict)
async def archive_coverage(
    coverage_id: int,
    _current_user: User = Depends(require_permission(_CATALOG_PERM)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Archiva una cobertura."""
    r = await db.execute(select(Coverage).where(Coverage.id == coverage_id))
    cov = r.scalar_one_or_none()
    if cov is None:
        raise HTTPException(status_code=404, detail="Cobertura no encontrada.")

    cov.status = "archived"
    await db.commit()
    return {"message": "Cobertura archivada correctamente."}


@catalog_router.post("/items/{coverage_id}/restore", response_model=CoverageDataResponse)
async def restore_coverage(
    coverage_id: int,
    _current_user: User = Depends(require_permission(_CATALOG_PERM)),
    db: AsyncSession = Depends(get_db),
) -> CoverageDataResponse:
    """Restaura una cobertura archivada."""
    r = await db.execute(
        select(Coverage).options(selectinload(Coverage.unit)).where(Coverage.id == coverage_id)
    )
    cov = r.scalar_one_or_none()
    if cov is None:
        raise HTTPException(status_code=404, detail="Cobertura no encontrada.")

    cov.status = "active"
    await db.commit()
    await db.refresh(cov)

    return CoverageDataResponse(data=_coverage_out(cov))


@catalog_router.delete("/items/{coverage_id}", response_model=dict)
async def destroy_coverage(
    coverage_id: int,
    _current_user: User = Depends(require_permission(_CATALOG_PERM)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Elimina una cobertura (si no está en uso en plan versions)."""
    r = await db.execute(
        select(Coverage)
        .options(selectinload(Coverage.plan_version_coverages))
        .where(Coverage.id == coverage_id)
    )
    cov = r.scalar_one_or_none()
    if cov is None:
        raise HTTPException(status_code=404, detail="Cobertura no encontrada.")

    if cov.plan_version_coverages:
        raise HTTPException(
            status_code=409,
            detail="La cobertura está en uso en versiones de plan y no puede eliminarse.",
        )

    await db.delete(cov)
    await db.commit()
    return {"message": "Cobertura eliminada correctamente."}


@catalog_router.get("/items/{coverage_id}/usages", response_model=dict)
async def coverage_usages(
    coverage_id: int,
    _current_user: User = Depends(require_permission(_CATALOG_PERM)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Lista versiones de plan que usan esta cobertura."""
    r = await db.execute(select(Coverage).where(Coverage.id == coverage_id))
    cov = r.scalar_one_or_none()
    if cov is None:
        raise HTTPException(status_code=404, detail="Cobertura no encontrada.")

    pvc_r = await db.execute(
        select(PlanVersionCoverage)
        .options(
            selectinload(PlanVersionCoverage.plan_version).selectinload(PlanVersion.product),
        )
        .where(PlanVersionCoverage.coverage_id == coverage_id)
        .order_by(PlanVersionCoverage.plan_version_id)
    )
    rows = pvc_r.scalars().all()

    usages = []
    for pvc in rows:
        pv = pvc.plan_version
        product = pv.product if pv else None
        usages.append(
            {
                "product_version_id": pvc.plan_version_id,
                "version_id": pv.id if pv else None,
                "product_id": product.id if product else None,
                "product_name": _pj(product.name) if product else None,
                "product_link": None,
                "version_link": None,
            }
        )

    return {"data": usages}


# ═════════════════════════════════════════════════════════════════════════════
# PLAN VERSION COVERAGES
# ═════════════════════════════════════════════════════════════════════════════


@pv_cov_router.get("/available", response_model=AvailableCoveragesResponse)
async def pv_available(
    product_id: int,
    version_id: int,
    _current_user: User = Depends(require_permission(_PV_PERM)),
    db: AsyncSession = Depends(get_db),
) -> AvailableCoveragesResponse:
    """Categorías/coberturas disponibles con flag 'attached'."""
    await _get_version(product_id, version_id, db)

    # IDs ya asociados
    attached_r = await db.execute(
        select(PlanVersionCoverage.coverage_id, PlanVersionCoverage.id).where(
            PlanVersionCoverage.plan_version_id == version_id
        )
    )
    attached_map = {row[0]: row[1] for row in attached_r.all()}

    cats_r = await db.execute(
        select(CoverageCategory)
        .options(selectinload(CoverageCategory.coverages).selectinload(Coverage.unit))
        .where(CoverageCategory.status == "active")
        .order_by(CoverageCategory.sort_order)
    )

    result = []
    for cat in cats_r.scalars().all():
        items = []
        for c in cat.coverages:
            if c.status != "active":
                continue
            items.append(
                AvailableCoverageItem(
                    id=c.id,
                    name=_pj(c.name),
                    description=_pj(c.description),
                    unit_id=c.unit_id,
                    unit_name=_pj(c.unit.name) if c.unit else None,
                    unit_measure_type=c.unit.measure_type if c.unit else None,
                    attached=c.id in attached_map,
                    plan_version_coverage_id=attached_map.get(c.id),
                )
            )
        result.append(AvailableCategoryOut(id=cat.id, name=_pj(cat.name), coverages=items))

    return AvailableCoveragesResponse(data=result)


@pv_cov_router.post("", response_model=PlanVersionCoverageDataResponse, status_code=201)
async def pv_store(
    product_id: int,
    version_id: int,
    body: StorePlanVersionCoverageRequest,
    _current_user: User = Depends(require_permission(_PV_PERM)),
    db: AsyncSession = Depends(get_db),
) -> PlanVersionCoverageDataResponse:
    """Agrega una cobertura a la versión de plan (idempotente)."""
    await _get_version(product_id, version_id, db)

    # Check duplicado
    existing_r = await db.execute(
        select(PlanVersionCoverage)
        .options(
            selectinload(PlanVersionCoverage.coverage).selectinload(Coverage.unit),
            selectinload(PlanVersionCoverage.coverage).selectinload(Coverage.category),
        )
        .where(
            PlanVersionCoverage.plan_version_id == version_id,
            PlanVersionCoverage.coverage_id == body.coverage_id,
        )
    )
    existing = existing_r.scalar_one_or_none()
    if existing:
        return PlanVersionCoverageDataResponse(data=_pv_coverage_out(existing))

    max_order = (
        await db.execute(
            select(func.coalesce(func.max(PlanVersionCoverage.sort_order), 0)).where(
                PlanVersionCoverage.plan_version_id == version_id
            )
        )
    ).scalar() or 0

    pvc = PlanVersionCoverage()
    pvc.plan_version_id = version_id
    pvc.coverage_id = body.coverage_id
    pvc.sort_order = max_order + 1

    db.add(pvc)
    await db.commit()

    r = await db.execute(
        select(PlanVersionCoverage)
        .options(
            selectinload(PlanVersionCoverage.coverage).selectinload(Coverage.unit),
            selectinload(PlanVersionCoverage.coverage).selectinload(Coverage.category),
        )
        .where(PlanVersionCoverage.id == pvc.id)
    )
    pvc = r.scalar_one()

    return PlanVersionCoverageDataResponse(data=_pv_coverage_out(pvc))


@pv_cov_router.delete("/{pvc_id}", response_model=dict)
async def pv_destroy(
    product_id: int,
    version_id: int,
    pvc_id: int,
    _current_user: User = Depends(require_permission(_PV_PERM)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Elimina una cobertura de la versión de plan."""
    await _get_version(product_id, version_id, db)

    r = await db.execute(
        select(PlanVersionCoverage).where(
            PlanVersionCoverage.id == pvc_id,
            PlanVersionCoverage.plan_version_id == version_id,
        )
    )
    pvc = r.scalar_one_or_none()
    if pvc is None:
        raise HTTPException(status_code=404, detail="Cobertura de versión no encontrada.")

    await db.delete(pvc)
    await db.commit()
    return {"message": "Cobertura eliminada de la versión."}


@pv_cov_router.post("/reorder", response_model=dict)
async def pv_reorder(
    product_id: int,
    version_id: int,
    body: ReorderPVCoveragesRequest,
    _current_user: User = Depends(require_permission(_PV_PERM)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reordena coberturas de la versión de plan."""
    await _get_version(product_id, version_id, db)

    for idx, cov_id in enumerate(body.coverage_ids):
        r = await db.execute(
            select(PlanVersionCoverage).where(
                PlanVersionCoverage.id == cov_id,
                PlanVersionCoverage.plan_version_id == version_id,
            )
        )
        pvc = r.scalar_one_or_none()
        if pvc:
            pvc.sort_order = idx + 1

    await db.commit()
    return {"message": "Orden actualizado correctamente."}


@pv_cov_router.patch("/{pvc_id}", response_model=PlanVersionCoverageDataResponse)
async def pv_update_value(
    product_id: int,
    version_id: int,
    pvc_id: int,
    body: UpdatePVCoverageValueRequest,
    _current_user: User = Depends(require_permission(_PV_PERM)),
    db: AsyncSession = Depends(get_db),
) -> PlanVersionCoverageDataResponse:
    """Actualiza el valor de una cobertura en la versión de plan."""
    await _get_version(product_id, version_id, db)

    r = await db.execute(
        select(PlanVersionCoverage)
        .options(
            selectinload(PlanVersionCoverage.coverage).selectinload(Coverage.unit),
            selectinload(PlanVersionCoverage.coverage).selectinload(Coverage.category),
        )
        .where(
            PlanVersionCoverage.id == pvc_id,
            PlanVersionCoverage.plan_version_id == version_id,
        )
    )
    pvc = r.scalar_one_or_none()
    if pvc is None:
        raise HTTPException(status_code=404, detail="Cobertura de versión no encontrada.")

    fields = body.model_fields_set
    if "value_int" in fields:
        pvc.value_int = body.value_int
    if "value_decimal" in fields:
        pvc.value_decimal = body.value_decimal
    if "value_text" in fields:
        pvc.value_text = _dj(body.value_text.model_dump()) if body.value_text else None
    if "notes" in fields:
        pvc.notes = _dj(body.notes.model_dump()) if body.notes else None

    await db.commit()
    await db.refresh(pvc)

    # Reload with relations
    r = await db.execute(
        select(PlanVersionCoverage)
        .options(
            selectinload(PlanVersionCoverage.coverage).selectinload(Coverage.unit),
            selectinload(PlanVersionCoverage.coverage).selectinload(Coverage.category),
        )
        .where(PlanVersionCoverage.id == pvc.id)
    )
    pvc = r.scalar_one()

    return PlanVersionCoverageDataResponse(data=_pv_coverage_out(pvc))
