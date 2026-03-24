"""
Controlador de Dashboard y Configuración (admin).
Equivale a DashboardController.php + ConfigController.php.

Endpoints Dashboard:
  GET    /admin/dashboard                              → dashboard

Endpoints Config:
  GET    /admin/config                                 → index
  POST   /admin/config                                 → store
  GET    /admin/config/{id}                            → show
  PUT    /admin/config/{id}/definition                 → updateDefinition
  PUT    /admin/config/{id}/value                      → updateValue
  DELETE /admin/config/{id}                            → destroy

Permisos: admin.config.read / admin.config.create / admin.config.edit / admin.config.fill / admin.config.delete
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.http.middleware.permission import require_permission
from app.http.requests.admin.config_request import (
    ConfigIndexResponse,
    ConfigItemDataResponse,
    ConfigItemMessageResponse,
    ConfigItemOut,
    DashboardResponse,
    StoreConfigItemRequest,
    UpdateDefinitionRequest,
    UpdateValueRequest,
)
from app.models.config_item import ConfigItem
from app.models.user import User

router = APIRouter(tags=["admin:config"])

_READ_PERM = "admin.config.read"
_CREATE_PERM = "admin.config.create"
_EDIT_PERM = "admin.config.edit"
_FILL_PERM = "admin.config.fill"
_DELETE_PERM = "admin.config.delete"


# ─────────────────────────── Helpers ─────────────────────────────────────────


def _item_out(item: ConfigItem) -> ConfigItemOut:
    return ConfigItemOut(
        id=item.id,
        category=item.category,
        token=item.token,
        name=item.name,
        type=item.type,
        config=item.config,
        value_int=item.value_int,
        value_decimal=float(item.value_decimal) if item.value_decimal is not None else None,
        value_text=item.value_text,
        value_trans=item.value_trans,
        value_date=str(item.value_date) if item.value_date else None,
        value_file_plain_id=item.value_file_plain_id,
        value_file_es_id=item.value_file_es_id,
        value_file_en_id=item.value_file_en_id,
    )


async def _get_item(item_id: int, db: AsyncSession) -> ConfigItem:
    r = await db.execute(select(ConfigItem).where(ConfigItem.id == item_id))
    item = r.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item de configuración no encontrado.")
    return item


# ─────────────────────────── Dashboard ───────────────────────────────────────


@router.get("/admin/dashboard", response_model=DashboardResponse)
async def dashboard(
    _current_user: User = Depends(require_permission(_READ_PERM)),
) -> DashboardResponse:
    """Dashboard placeholder — se expandirá con métricas en el futuro."""
    return DashboardResponse()


# ─────────────────────────── Config: index ───────────────────────────────────


@router.get("/admin/config", response_model=ConfigIndexResponse)
async def config_index(
    _current_user: User = Depends(require_permission(_READ_PERM)),
    db: AsyncSession = Depends(get_db),
) -> ConfigIndexResponse:
    """Lista todos los items de configuración."""
    r = await db.execute(
        select(ConfigItem).order_by(ConfigItem.category, ConfigItem.name)
    )
    items = [_item_out(i) for i in r.scalars().all()]

    return ConfigIndexResponse(
        items=items,
        permissions={
            "create": True,
            "read": True,
            "fill": True,
            "edit": True,
            "delete": True,
        },
    )


# ─────────────────────────── Config: store ───────────────────────────────────


@router.post("/admin/config", response_model=ConfigItemMessageResponse, status_code=201)
async def config_store(
    body: StoreConfigItemRequest,
    _current_user: User = Depends(require_permission(_CREATE_PERM)),
    db: AsyncSession = Depends(get_db),
) -> ConfigItemMessageResponse:
    """Crea un nuevo item de configuración."""
    # Validar token único por categoría
    existing = await db.execute(
        select(ConfigItem).where(
            ConfigItem.category == body.category,
            ConfigItem.token == body.token,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="El token ya existe en esta categoría.")

    item = ConfigItem()
    item.category = body.category
    item.name = body.name
    item.token = body.token
    item.type = body.type
    item.config = json.dumps(body.config) if body.config else None

    db.add(item)
    await db.commit()
    await db.refresh(item)

    return ConfigItemMessageResponse(item=_item_out(item), message="Item creado correctamente.")


# ─────────────────────────── Config: show ────────────────────────────────────


@router.get("/admin/config/{item_id}", response_model=ConfigItemDataResponse)
async def config_show(
    item_id: int,
    _current_user: User = Depends(require_permission(_READ_PERM)),
    db: AsyncSession = Depends(get_db),
) -> ConfigItemDataResponse:
    """Detalle de un item de configuración."""
    item = await _get_item(item_id, db)
    return ConfigItemDataResponse(item=_item_out(item))


# ─────────────────────────── Config: updateDefinition ────────────────────────


@router.put("/admin/config/{item_id}/definition", response_model=ConfigItemMessageResponse)
async def config_update_definition(
    item_id: int,
    body: UpdateDefinitionRequest,
    _current_user: User = Depends(require_permission(_EDIT_PERM)),
    db: AsyncSession = Depends(get_db),
) -> ConfigItemMessageResponse:
    """Actualiza la definición (nombre, token, tipo, config) de un item."""
    item = await _get_item(item_id, db)
    fields = body.model_fields_set

    if "token" in fields and body.token:
        # Validar token único excluyendo el actual
        clash = await db.execute(
            select(ConfigItem).where(
                ConfigItem.category == (body.category or item.category),
                ConfigItem.token == body.token,
                ConfigItem.id != item_id,
            )
        )
        if clash.scalar_one_or_none() is not None:
            raise HTTPException(status_code=422, detail="El token ya existe en esta categoría.")
        item.token = body.token

    if "category" in fields:
        item.category = body.category
    if "name" in fields:
        item.name = body.name
    if "type" in fields:
        item.type = body.type
    if "config" in fields:
        item.config = json.dumps(body.config) if body.config else None

    await db.commit()
    await db.refresh(item)

    return ConfigItemMessageResponse(item=_item_out(item), message="Definición actualizada.")


# ─────────────────────────── Config: updateValue ─────────────────────────────


@router.put("/admin/config/{item_id}/value", response_model=ConfigItemMessageResponse)
async def config_update_value(
    item_id: int,
    body: UpdateValueRequest,
    _current_user: User = Depends(require_permission(_FILL_PERM)),
    db: AsyncSession = Depends(get_db),
) -> ConfigItemMessageResponse:
    """Actualiza el valor de un item según su tipo."""
    item = await _get_item(item_id, db)
    val = body.value

    item_type = item.type

    if item_type in ("integer", "boolean"):
        item.value_int = int(val) if val is not None else None
    elif item_type == "decimal":
        item.value_decimal = float(val) if val is not None else None
    elif item_type == "date":
        item.value_date = val
    elif item_type in (
        "input_text_translated", "textarea_translated", "html_translated",
    ):
        item.value_trans = json.dumps(val, ensure_ascii=False) if val else None
    elif item_type in (
        "input_text_plain", "textarea_plain", "html_plain",
        "email", "url", "phone", "color", "json",
        "model_reference", "enum",
    ):
        item.value_text = val
    else:
        item.value_text = str(val) if val is not None else None

    await db.commit()
    await db.refresh(item)

    return ConfigItemMessageResponse(item=_item_out(item), message="Valor actualizado.")


# ─────────────────────────── Config: destroy ─────────────────────────────────


@router.delete("/admin/config/{item_id}", response_model=dict)
async def config_destroy(
    item_id: int,
    _current_user: User = Depends(require_permission(_DELETE_PERM)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Elimina un item de configuración."""
    item = await _get_item(item_id, db)
    await db.delete(item)
    await db.commit()
    return {"toast": {"type": "success", "message": "Item eliminado."}}
