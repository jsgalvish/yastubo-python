"""
Controlador de productos (admin).
Equivale a ProductController.php en Laravel.

Endpoints:
  GET    /admin/products              → index  (solo plan_regular)
  POST   /admin/products              → store
  GET    /admin/products/{id}         → show
  PUT    /admin/products/{id}         → update

Permiso requerido: admin.products.manage

Cambios aplicados por auditoría de skills:
  - HIGH-2: response_model tipados (Pydantic, no dict)
  - MED-7: _actor → _current_user
  - MED-8: type hints en helpers
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_db
from common.middleware.permission import require_permission
from common.models.product import Product
from common.models.user import User

from ..requests.product_request import (
    ProductDataResponse,
    ProductDataToastResponse,
    ProductIndexResponse,
    ProductOut,
    StoreProductRequest,
    UpdateProductRequest,
)

router = APIRouter(prefix="/admin/products", tags=["admin:products"])

_PERMISSION = "admin.products.manage"


# ─────────────────────────── Helpers ─────────────────────────────────────────


def _parse_json(value: str | None) -> dict | None:
    """Parsea un campo JSON almacenado como string."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return None


def _build_product_out(product: Product) -> ProductOut:
    """Equivale a transformProduct() en PHP."""
    return ProductOut(
        id=product.id,
        company_id=product.company_id,
        status=product.status,
        product_type=product.product_type,
        show_in_widget=product.show_in_widget,
        name=_parse_json(product.name),
        description=_parse_json(product.description),
    )


async def _get_product(product_id: int, db: AsyncSession) -> Product:
    """Carga un producto por ID. 404 si no existe."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    return product


# ─────────────────────────── index ───────────────────────────────────────────


@router.get("", response_model=ProductIndexResponse)
async def index(
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> ProductIndexResponse:
    """
    Lista de productos de tipo plan_regular, ordenados por id desc.
    Equivale a index() en PHP (filtra solo TYPE_PLAN_REGULAR).
    """
    result = await db.execute(
        select(Product)
        .where(Product.product_type == Product.TYPE_PLAN_REGULAR)
        .order_by(Product.id.desc())
    )
    products = list(result.scalars().all())

    return ProductIndexResponse(
        products=[_build_product_out(p) for p in products],
        product_type_options=Product.types(),
    )


# ─────────────────────────── store ───────────────────────────────────────────


@router.post("", response_model=ProductDataResponse, status_code=201)
async def store(
    body: StoreProductRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> ProductDataResponse:
    """
    Crea un nuevo producto. Equivale a store() en PHP.

    Reglas de consistencia tipo/empresa:
      - plan_capitado: DEBE tener company_id
      - plan_regular: NO puede tener company_id
    """
    if body.product_type == Product.TYPE_PLAN_CAPITADO and body.company_id is None:
        raise HTTPException(
            status_code=422,
            detail="Un producto capitado debe tener una empresa asociada (company_id).",
        )

    if body.product_type == Product.TYPE_PLAN_REGULAR and body.company_id is not None:
        raise HTTPException(
            status_code=422,
            detail="Un producto regular no puede tener empresa asociada (company_id).",
        )

    product = Product()
    product.name = json.dumps(body.name.model_dump(), ensure_ascii=False)
    product.description = (
        json.dumps(body.description.model_dump(), ensure_ascii=False) if body.description else None
    )
    product.product_type = body.product_type
    product.show_in_widget = body.show_in_widget
    product.company_id = body.company_id
    product.status = "inactive"  # siempre inactivo al crear

    db.add(product)
    await db.commit()
    await db.refresh(product)

    return ProductDataResponse(data=_build_product_out(product))


# ─────────────────────────── show ────────────────────────────────────────────


@router.get("/{product_id}", response_model=ProductDataResponse)
async def show(
    product_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> ProductDataResponse:
    """Detalle de un producto. Equivale a show() en PHP."""
    product = await _get_product(product_id, db)
    return ProductDataResponse(data=_build_product_out(product))


# ─────────────────────────── update ──────────────────────────────────────────


@router.put("/{product_id}", response_model=ProductDataToastResponse)
async def update(
    product_id: int,
    body: UpdateProductRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> ProductDataToastResponse:
    """
    Actualiza un producto. Equivale a update() en PHP.
    product_type y company_id NO son modificables después de la creación.
    """
    product = await _get_product(product_id, db)
    fields = body.model_fields_set

    if "name" in fields and body.name is not None:
        product.name = json.dumps(body.name.model_dump(), ensure_ascii=False)

    if "description" in fields:
        product.description = (
            json.dumps(body.description.model_dump(), ensure_ascii=False)
            if body.description
            else None
        )

    if "show_in_widget" in fields and body.show_in_widget is not None:
        product.show_in_widget = body.show_in_widget

    if "status" in fields and body.status is not None:
        product.status = body.status

    await db.commit()
    await db.refresh(product)

    return ProductDataToastResponse(
        data=_build_product_out(product),
        toast={"type": "success", "message": "Producto actualizado correctamente."},
    )
