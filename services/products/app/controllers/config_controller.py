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
  POST   /admin/config/{id}/file                       → uploadFile

Permisos: admin.config.read / admin.config.create / admin.config.edit / admin.config.fill / admin.config.delete
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.requests.config_request import (
    BatchCard,
    BeneficiarioStats,
    CompanyCard,
    ConfigIndexResponse,
    ConfigItemDataResponse,
    ConfigItemMessageResponse,
    ConfigItemOut,
    DashboardResponse,
    RetailStats,
    StoreConfigItemRequest,
    UpdateDefinitionRequest,
    UpdateValueRequest,
)
from common.database import get_db
from common.middleware.permission import require_permission
from common.models.capitated_batch_log import CapitatedBatchLog
from common.models.capitated_product_insured import CapitatedProductInsured
from common.models.company import Company
from common.models.config_item import ConfigItem
from common.models.plan_version import PlanVersion
from common.models.subscription import Subscription
from common.models.user import User

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
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """Métricas de negocio reales para el dashboard de admin."""

    # ── Beneficiarios capitados por status ────────────────────────────────────
    rows_status = list(
        (
            await db.execute(
                select(CapitatedProductInsured.status, func.count().label("cnt")).group_by(
                    CapitatedProductInsured.status
                )
            )
        ).all()
    )

    active = sum(r.cnt for r in rows_status if r.status == "active")
    rolled_back = sum(r.cnt for r in rows_status if r.status == "rolled_back")
    other = sum(r.cnt for r in rows_status if r.status not in ("active", "rolled_back"))
    total_beneficiarios = active + rolled_back + other

    # ── MRR estimado: personas activas × precio promedio de plan activo ───────  # noqa: RUF003
    pv_prices = list(
        (
            await db.execute(
                select(PlanVersion.public_price).where(
                    PlanVersion.status == "active", PlanVersion.public_price.isnot(None)
                )
            )
        )
        .scalars()
        .all()
    )
    avg_price = float(sum(pv_prices) / len(pv_prices)) if pv_prices else 14.99
    mrr_estimate = round(active * avg_price, 2)

    # ── Empresas con branding ─────────────────────────────────────────────────
    companies_rows = list(
        (await db.execute(select(Company).order_by(Company.status.desc(), Company.name)))
        .scalars()
        .all()
    )

    companies = [
        CompanyCard(
            id=c.id,
            name=c.name,
            short_code=c.short_code,
            status=c.status or "unknown",
            logo_file_id=c.branding_logo_file_id,
        )
        for c in companies_rows
    ]

    # ── Lotes recientes (batches) ─────────────────────────────────────────────
    batch_rows = list(
        (
            await db.execute(
                select(CapitatedBatchLog, Company.name.label("company_name"))
                .join(Company, CapitatedBatchLog.company_id == Company.id)
                .order_by(CapitatedBatchLog.coverage_month.desc())
                .limit(6)
            )
        ).all()
    )

    recent_batches = [
        BatchCard(
            id=row.CapitatedBatchLog.id,
            company_id=row.CapitatedBatchLog.company_id,
            company_name=row.company_name,
            coverage_month=str(row.CapitatedBatchLog.coverage_month),
            status=row.CapitatedBatchLog.status,
            total_rows=row.CapitatedBatchLog.total_rows,
            total_applied=row.CapitatedBatchLog.total_applied,
            total_rejected=row.CapitatedBatchLog.total_rejected,
        )
        for row in batch_rows
    ]

    # ── Retail subscriptions (Module F) ─────────────────────────────────
    total_subs = (
        await db.execute(select(func.count()).select_from(select(Subscription).subquery()))
    ).scalar() or 0
    active_subs = (
        await db.execute(
            select(func.count()).select_from(
                select(Subscription).where(Subscription.status == "active").subquery()
            )
        )
    ).scalar() or 0
    mrr_retail = (
        await db.execute(
            select(func.sum(Subscription.amount_cents)).where(Subscription.status == "active")
        )
    ).scalar() or 0

    return DashboardResponse(
        beneficiarios=BeneficiarioStats(
            active=active,
            rolled_back=rolled_back,
            other=other,
            total=total_beneficiarios,
        ),
        mrr_capitado=mrr_estimate,
        mrr_retail_cents=mrr_retail,
        retail=RetailStats(
            total_subscriptions=total_subs,
            active=active_subs,
            mrr_cents=mrr_retail,
        ),
        companies=companies,
        recent_batches=recent_batches,
    )


# ─────────────────────────── Config: index ───────────────────────────────────


@router.get("/admin/config", response_model=ConfigIndexResponse)
async def config_index(
    _current_user: User = Depends(require_permission(_READ_PERM)),
    db: AsyncSession = Depends(get_db),
) -> ConfigIndexResponse:
    """Lista todos los items de configuración."""
    r = await db.execute(select(ConfigItem).order_by(ConfigItem.category, ConfigItem.name))
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
        "input_text_translated",
        "textarea_translated",
        "html_translated",
    ):
        item.value_trans = json.dumps(val, ensure_ascii=False) if val else None
    elif item_type in (
        "input_text_plain",
        "textarea_plain",
        "html_plain",
        "email",
        "url",
        "phone",
        "color",
        "json",
        "model_reference",
        "enum",
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


# ─────────────────────────── Config: uploadFile ──────────────────────────────


@router.post("/admin/config/{item_id}/upload", response_model=ConfigItemMessageResponse)
async def config_upload_file(
    item_id: int,
    file: UploadFile = File(...),
    locale: str | None = Query(default=None),
    _current_user: User = Depends(require_permission(_FILL_PERM)),
    db: AsyncSession = Depends(get_db),
) -> ConfigItemMessageResponse:
    """Sube un archivo para un item de configuración de tipo file."""
    item = await _get_item(item_id, db)

    if item.type not in ("file_plain", "file_translated"):
        raise HTTPException(status_code=422, detail="Este registro no es de tipo archivo.")

    from common.services.uploaded_file.uploaded_file_service import UploadedFileService

    uploader = UploadedFileService(db)
    user_id = _current_user.id

    meta = {
        "context": "config_item",
        "model": "ConfigItem",
        "model_id": item.id,
    }

    # Determinar campo según tipo
    if item.type == "file_plain":
        field = "value_file_plain_id"
        current_file_id = item.value_file_plain_id
        meta["field"] = "value_file_plain_id"
        meta["lang"] = None
    else:
        effective_locale = locale or "es"
        if effective_locale == "es":
            field = "value_file_es_id"
            current_file_id = item.value_file_es_id
            meta["field"] = "value_file_es_id"
            meta["lang"] = "es"
        else:
            field = "value_file_en_id"
            current_file_id = item.value_file_en_id
            meta["field"] = "value_file_en_id"
            meta["lang"] = "en"

    base_path = f"config/{item.id}/{field}"

    if current_file_id:
        from common.models.file import File as FileModel

        r = await db.execute(select(FileModel).where(FileModel.id == current_file_id))
        current = r.scalar_one_or_none()
        if current:
            file_model = await uploader.replace(
                current,
                file,
                meta=meta,
                uploaded_by_user_id=user_id,
                base_path=base_path,
            )
        else:
            file_model = await uploader.store(
                file,
                meta=meta,
                uploaded_by_user_id=user_id,
                base_path=base_path,
            )
            setattr(item, field, file_model.id)
    else:
        file_model = await uploader.store(
            file,
            meta=meta,
            uploaded_by_user_id=user_id,
            base_path=base_path,
        )
        setattr(item, field, file_model.id)

    await db.commit()
    await db.refresh(item)

    return ConfigItemMessageResponse(item=_item_out(item), message="Archivo subido correctamente.")


@router.delete("/admin/config/{item_id}/file", status_code=200)
async def config_delete_file(
    item_id: int,
    locale: str | None = Query(default=None),
    _current_user: User = Depends(require_permission(_FILL_PERM)),
    db: AsyncSession = Depends(get_db),
):
    """Elimina el archivo asociado a un item de configuración."""
    item = await _get_item(item_id, db)

    if item.type not in ("file_plain", "file_translated"):
        raise HTTPException(status_code=422, detail="Este registro no es de tipo archivo.")

    if item.type == "file_plain":
        field = "value_file_plain_id"
    else:
        effective_locale = locale or "es"
        field = "value_file_es_id" if effective_locale == "es" else "value_file_en_id"

    current_file_id = getattr(item, field, None)
    if not current_file_id:
        raise HTTPException(status_code=404, detail="No hay archivo asociado.")

    from common.models.file import File as FileModel
    from common.services.uploaded_file.uploaded_file_service import UploadedFileService

    r = await db.execute(select(FileModel).where(FileModel.id == current_file_id))
    file_model = r.scalar_one_or_none()

    if file_model:
        uploader = UploadedFileService(db)
        await uploader.delete(file_model, delete_physical=True)

    setattr(item, field, None)
    await db.commit()

    return {"toast": {"type": "success", "message": "Archivo eliminado."}}
