"""
Controlador de versiones de plan + recargos por edad (admin).
Equivale a PlanVersionController.php + PlanVersionAgeSurchargeController.php.

Endpoints PlanVersion:
  GET    /admin/products/{pid}/plans                         → index
  POST   /admin/products/{pid}/plans                         → store
  GET    /admin/products/{pid}/plans/{vid}                   → show (edit)
  PUT    /admin/products/{pid}/plans/{vid}                   → update
  DELETE /admin/products/{pid}/plans/{vid}                   → destroy
  POST   /admin/products/{pid}/plans/{vid}/clone             → clone
  GET    /admin/products/{pid}/plans/{vid}/pdf               → pdfPreview
  GET    /admin/products/{pid}/plans/{vid}/terms-html        → showTermsHtml
  PATCH  /admin/products/{pid}/plans/{vid}/terms-html        → updateTermsHtml

Endpoints AgeSurcharge:
  GET    /admin/products/{pid}/plans/{vid}/age-surcharges              → index
  POST   /admin/products/{pid}/plans/{vid}/age-surcharges              → store
  PATCH  /admin/products/{pid}/plans/{vid}/age-surcharges/{sid}        → update
  DELETE /admin/products/{pid}/plans/{vid}/age-surcharges/{sid}        → destroy

Permiso requerido: admin.products.manage

Skills aplicados:
  - FastAPI: response models tipados, _current_user, type hints
  - Pydantic: Literal types, ConfigDict
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.http.middleware.permission import require_permission
from app.http.requests.admin.plan_version_request import (
    AgeSurchargeDataResponse,
    AgeSurchargeDeleteResponse,
    AgeSurchargeIndexResponse,
    AgeSurchargeOut,
    ClonePlanVersionRequest,
    PlanVersionDataResponse,
    PlanVersionDataToastResponse,
    PlanVersionDeleteResponse,
    PlanVersionIndexResponse,
    PlanVersionOut,
    StoreAgeSurchargeRequest,
    StorePlanVersionRequest,
    TermsHtmlDataResponse,
    UpdateAgeSurchargeRequest,
    UpdatePlanVersionRequest,
    UpdateTermsHtmlRequest,
)
from app.models.plan_version import PlanVersion
from app.models.plan_version_age_surcharge import PlanVersionAgeSurcharge
from app.models.product import Product
from app.models.user import User

router = APIRouter(
    prefix="/admin/products/{product_id}/plans",
    tags=["admin:plan-versions"],
)

_PERMISSION = "admin.products.manage"


# ─────────────────────────── Helpers ─────────────────────────────────────────


async def _get_product(product_id: int, db: AsyncSession) -> Product:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    return product


async def _get_version(
    product_id: int, version_id: int, db: AsyncSession
) -> PlanVersion:
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


async def _get_surcharge(
    product_id: int, version_id: int, surcharge_id: int, db: AsyncSession
) -> PlanVersionAgeSurcharge:
    version = await _get_version(product_id, version_id, db)
    result = await db.execute(
        select(PlanVersionAgeSurcharge).where(
            PlanVersionAgeSurcharge.id == surcharge_id,
            PlanVersionAgeSurcharge.plan_version_id == version.id,
        )
    )
    surcharge = result.scalar_one_or_none()
    if surcharge is None:
        raise HTTPException(status_code=404, detail="Recargo por edad no encontrado.")
    return surcharge


def _build_version_out(v: PlanVersion) -> PlanVersionOut:
    return PlanVersionOut(
        id=v.id,
        product_id=v.product_id,
        name=v.name,
        status=v.status,
        max_entry_age=v.max_entry_age,
        max_renewal_age=v.max_renewal_age,
        wtime_suicide=v.wtime_suicide,
        wtime_preexisting_conditions=v.wtime_preexisting_conditions,
        wtime_accident=v.wtime_accident,
        country_id=v.country_id,
        zone_id=v.zone_id,
        price_1=float(v.price_1) if v.price_1 is not None else None,
        price_2=float(v.price_2) if v.price_2 is not None else None,
        price_3=float(v.price_3) if v.price_3 is not None else None,
        price_4=float(v.price_4) if v.price_4 is not None else None,
        terms_file_es_id=v.terms_file_es_id,
        terms_file_en_id=v.terms_file_en_id,
        can_be_activated=v.can_be_activated(),
        is_in_use=v.is_in_use(),
        is_deletable=v.is_deletable(),
    )


def _build_surcharge_out(s: PlanVersionAgeSurcharge) -> AgeSurchargeOut:
    return AgeSurchargeOut(
        id=s.id,
        plan_version_id=s.plan_version_id,
        age_from=s.age_from,
        age_to=s.age_to,
        surcharge_percent=float(s.surcharge_percent) if s.surcharge_percent is not None else None,
    )


def _parse_terms_html(raw: str | None) -> dict:
    """Parsea terms_html JSON → {es, en}. Soporta legacy (string plano = ES)."""
    if raw is None:
        return {"es": None, "en": None}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {"es": data.get("es"), "en": data.get("en")}
    except (json.JSONDecodeError, ValueError):
        pass
    # Legacy: string plano = ES
    return {"es": raw, "en": None}


# ─────────────────────────── PlanVersion: index ──────────────────────────────


@router.get("", response_model=PlanVersionIndexResponse)
async def index(
    product_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> PlanVersionIndexResponse:
    """Lista versiones de plan para un producto, ordenadas por id desc."""
    await _get_product(product_id, db)
    result = await db.execute(
        select(PlanVersion)
        .where(PlanVersion.product_id == product_id)
        .order_by(PlanVersion.id.desc())
    )
    versions = list(result.scalars().all())
    return PlanVersionIndexResponse(data=[_build_version_out(v) for v in versions])


# ─────────────────────────── PlanVersion: store ──────────────────────────────


@router.post("", response_model=PlanVersionDataResponse, status_code=201)
async def store(
    product_id: int,
    body: StorePlanVersionRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> PlanVersionDataResponse:
    """Crea una nueva versión de plan (siempre inactive)."""
    await _get_product(product_id, db)

    version = PlanVersion()
    version.product_id = product_id
    version.name = body.name.strip()
    version.status = PlanVersion.STATUS_INACTIVE

    db.add(version)
    await db.commit()
    await db.refresh(version)

    return PlanVersionDataResponse(data=_build_version_out(version))


# ─────────────────────────── PlanVersion: show ───────────────────────────────


@router.get("/{version_id}", response_model=PlanVersionDataResponse)
async def show(
    product_id: int,
    version_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> PlanVersionDataResponse:
    """Detalle de una versión de plan."""
    version = await _get_version(product_id, version_id, db)
    return PlanVersionDataResponse(data=_build_version_out(version))


# ─────────────────────────── PlanVersion: update ─────────────────────────────


@router.put("/{version_id}", response_model=PlanVersionDataToastResponse)
async def update(
    product_id: int,
    version_id: int,
    body: UpdatePlanVersionRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> PlanVersionDataToastResponse:
    """
    Actualización parcial de versión de plan.
    Si se activa, desactiva las demás versiones del mismo producto.
    """
    version = await _get_version(product_id, version_id, db)
    fields = body.model_fields_set
    original_status = version.status

    for field in fields:
        value = getattr(body, field)
        if value is not None or field in (
            "country_id", "zone_id", "terms_file_es_id", "terms_file_en_id",
            "max_entry_age", "max_renewal_age",
            "wtime_suicide", "wtime_preexisting_conditions", "wtime_accident",
            "price_1", "price_2", "price_3", "price_4",
        ):
            setattr(version, field, value)

    # Si se activa, desactivar las demás versiones del mismo producto
    new_status = version.status
    if new_status == PlanVersion.STATUS_ACTIVE and original_status != PlanVersion.STATUS_ACTIVE:
        await db.execute(
            sa_update(PlanVersion)
            .where(
                PlanVersion.product_id == product_id,
                PlanVersion.id != version_id,
                PlanVersion.status == PlanVersion.STATUS_ACTIVE,
            )
            .values(status=PlanVersion.STATUS_INACTIVE)
        )

    await db.commit()
    await db.refresh(version)

    return PlanVersionDataToastResponse(
        data=_build_version_out(version),
        toast={"type": "success", "message": "Versión actualizada correctamente."},
    )


# ─────────────────────────── PlanVersion: destroy ────────────────────────────


@router.delete("/{version_id}", response_model=PlanVersionDeleteResponse)
async def destroy(
    product_id: int,
    version_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> PlanVersionDeleteResponse:
    """Elimina una versión de plan (si no está en uso)."""
    version = await _get_version(product_id, version_id, db)

    if not version.is_deletable():
        raise HTTPException(status_code=422, detail="La versión está en uso y no puede eliminarse.")

    await db.delete(version)
    await db.commit()

    return PlanVersionDeleteResponse(message="Versión eliminada correctamente.")


# ─────────────────────────── PlanVersion: clone ──────────────────────────────


@router.post("/{version_id}/clone", response_model=PlanVersionDataResponse, status_code=201)
async def clone(
    product_id: int,
    version_id: int,
    body: ClonePlanVersionRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> PlanVersionDataResponse:
    """Clona una versión de plan con nuevo nombre (siempre inactive)."""
    source = await _get_version(product_id, version_id, db)

    new_version = PlanVersion()
    new_version.product_id = product_id
    new_version.name = body.name.strip()
    new_version.status = PlanVersion.STATUS_INACTIVE

    # Copiar campos configurables
    for field in (
        "max_entry_age", "max_renewal_age",
        "wtime_suicide", "wtime_preexisting_conditions", "wtime_accident",
        "country_id", "zone_id",
        "price_1", "price_2", "price_3", "price_4",
        "terms_html",
    ):
        setattr(new_version, field, getattr(source, field))

    db.add(new_version)
    await db.flush()

    # Clonar age surcharges
    surcharges_result = await db.execute(
        select(PlanVersionAgeSurcharge)
        .where(PlanVersionAgeSurcharge.plan_version_id == source.id)
    )
    for s in surcharges_result.scalars().all():
        clone_s = PlanVersionAgeSurcharge()
        clone_s.plan_version_id = new_version.id
        clone_s.age_from = s.age_from
        clone_s.age_to = s.age_to
        clone_s.surcharge_percent = s.surcharge_percent
        db.add(clone_s)

    await db.commit()
    await db.refresh(new_version)

    return PlanVersionDataResponse(data=_build_version_out(new_version))


# ─────────────────────────── PlanVersion: pdf ─────────────────────────────────


@router.get("/{version_id}/pdf")
async def pdf_preview(
    product_id: int,
    version_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Genera un PDF de preview para la versión de plan."""
    from app.models.coverage import Coverage
    from app.models.file import File as FileModel
    from app.models.plan_version_coverage import PlanVersionCoverage
    from app.models.template import Template
    from app.models.template_version import TemplateVersion
    from app.services.pdf.pdf_service import html_to_pdf_async
    from app.services.template_render.template_render_service import TemplateRenderService
    from app.support.json_decode import JsonDecode

    version = await _get_version(product_id, version_id, db)
    product_r = await db.execute(
        select(Product)
        .options(selectinload(Product.company))
        .where(Product.id == product_id)
    )
    product = product_r.scalar_one()

    # Cargar coberturas con relaciones
    pvc_r = await db.execute(
        select(PlanVersionCoverage)
        .options(
            selectinload(PlanVersionCoverage.coverage)
            .selectinload(Coverage.unit),
            selectinload(PlanVersionCoverage.coverage)
            .selectinload(Coverage.category),
        )
        .where(PlanVersionCoverage.plan_version_id == version_id)
        .order_by(PlanVersionCoverage.sort_order)
    )
    pv_coverages = list(pvc_r.scalars().all())

    # Construir categorías de coberturas
    categories: dict[int, dict] = {}
    for pivot in pv_coverages:
        cov = pivot.coverage
        if not cov:
            continue
        cat = cov.category
        if not cat:
            continue
        cat_id = cat.id
        if cat_id not in categories:
            categories[cat_id] = {
                "id": cat_id,
                "sort_order": cat.sort_order or 0,
                "name": cat.name,
                "description": cat.description,
                "coverages": [],
            }
        unit = cov.unit
        categories[cat_id]["coverages"].append({
            "id": pivot.id,
            "plan_version_id": pivot.plan_version_id,
            "coverage_id": pivot.coverage_id,
            "sort_order": pivot.sort_order,
            "value_int": pivot.value_int,
            "value_decimal": float(pivot.value_decimal) if pivot.value_decimal is not None else None,
            "value_text": JsonDecode.get(pivot.value_text),
            "notes": JsonDecode.get(pivot.notes),
            "coverage_name": cov.name,
            "coverage_description": cov.description,
            "unit_name": unit.name if unit else None,
            "unit_measure_type": unit.measure_type if unit else None,
        })

    coverage_categories = sorted(categories.values(), key=lambda c: c["sort_order"])

    # Buscar template y versión activa
    company = product.company
    id_contrato = "YTB-000001"
    emitido_por = "Nombre Emisor"
    branding: dict = {}
    template = None

    if company:
        id_contrato = f"{company.short_code}-000001" if company.short_code else "YTB-000001"
        emitido_por = company.name or "Nombre Emisor"

        # Buscar template de la empresa o el default "principal"
        if company.pdf_template_id:
            t_r = await db.execute(
                select(Template).where(Template.id == company.pdf_template_id)
            )
            template = t_r.scalar_one_or_none()

        if not template:
            t_r = await db.execute(
                select(Template).where(Template.slug == "principal", Template.deleted_at.is_(None))
            )
            template = t_r.scalar_one_or_none()

        # Branding de la empresa
        from app.models.config_item import ConfigItem

        config_r = await db.execute(
            select(ConfigItem).where(ConfigItem.category == "company_branding")
        )
        for ci in config_r.scalars().all():
            val = ci.get_value()
            if ci.token == "logo" and ci.type == "file" and ci.value_file_plain_id:
                logo_r = await db.execute(
                    select(FileModel).where(FileModel.id == ci.value_file_plain_id)
                )
                logo_file = logo_r.scalar_one_or_none()
                branding["logo"] = logo_file.local_path() if logo_file else ""
            elif val is not None:
                if ci.token in ("text_dark", "text_light", "bg_light", "bg_dark"):
                    branding[ci.token] = "#" + str(val).lstrip("#")
                else:
                    branding[ci.token] = val
    else:
        # Sin empresa: template default
        t_r = await db.execute(
            select(Template).where(Template.slug == "principal", Template.deleted_at.is_(None))
        )
        template = t_r.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=503, detail="Template principal no encontrado.")

    if not template.active_template_version_id:
        raise HTTPException(status_code=504, detail="No hay versión activa del template.")

    tv_r = await db.execute(
        select(TemplateVersion).where(
            TemplateVersion.id == template.active_template_version_id,
            TemplateVersion.template_id == template.id,
        )
    )
    template_version = tv_r.scalar_one_or_none()
    if not template_version:
        raise HTTPException(status_code=504, detail="Versión activa del template no encontrada.")

    # Construir datos para el template
    data = JsonDecode.get(template.test_data_json)
    if not isinstance(data, dict):
        data = {}

    data["product"] = product
    data["planVersion"] = version
    data["coverageCategories"] = coverage_categories
    if "contrato" not in data:
        data["contrato"] = {}
    data["contrato"]["id"] = id_contrato
    data["contrato"]["emitido_por"] = emitido_por
    data["contrato"]["codigo_plan"] = f"{product.id}v{version.id}"
    data["branding"] = branding

    render_service = TemplateRenderService(db)
    html = render_service.render_template(template_version.content, data)
    binary = await html_to_pdf_async(html)

    return Response(content=binary, media_type="application/pdf")


# ─────────────────────────── Terms HTML ──────────────────────────────────────


@router.get("/{version_id}/terms-html", response_model=TermsHtmlDataResponse)
async def show_terms_html(
    product_id: int,
    version_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> TermsHtmlDataResponse:
    """Retorna terms_html como {es, en}."""
    version = await _get_version(product_id, version_id, db)
    return TermsHtmlDataResponse(data={"terms_html": _parse_terms_html(version.terms_html)})


@router.patch("/{version_id}/terms-html", response_model=TermsHtmlDataResponse)
async def update_terms_html(
    product_id: int,
    version_id: int,
    body: UpdateTermsHtmlRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> TermsHtmlDataResponse:
    """Actualiza terms_html para un locale específico (es o en)."""
    version = await _get_version(product_id, version_id, db)

    current = _parse_terms_html(version.terms_html)
    current[body.locale] = body.html

    version.terms_html = json.dumps(current, ensure_ascii=False)
    await db.commit()
    await db.refresh(version)

    return TermsHtmlDataResponse(data={"terms_html": _parse_terms_html(version.terms_html)})


# ─────────────────────────── AgeSurcharge: index ─────────────────────────────


@router.get("/{version_id}/age-surcharges", response_model=AgeSurchargeIndexResponse)
async def age_surcharges_index(
    product_id: int,
    version_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> AgeSurchargeIndexResponse:
    """Lista recargos por edad de una versión, ordenados por age_from."""
    await _get_version(product_id, version_id, db)
    result = await db.execute(
        select(PlanVersionAgeSurcharge)
        .where(PlanVersionAgeSurcharge.plan_version_id == version_id)
        .order_by(PlanVersionAgeSurcharge.age_from, PlanVersionAgeSurcharge.age_to)
    )
    items = list(result.scalars().all())
    return AgeSurchargeIndexResponse(data=[_build_surcharge_out(s) for s in items])


# ─────────────────────────── AgeSurcharge: store ─────────────────────────────


@router.post("/{version_id}/age-surcharges", response_model=AgeSurchargeDataResponse, status_code=201)
async def age_surcharges_store(
    product_id: int,
    version_id: int,
    body: StoreAgeSurchargeRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> AgeSurchargeDataResponse:
    """Crea un recargo por edad."""
    await _get_version(product_id, version_id, db)

    surcharge = PlanVersionAgeSurcharge()
    surcharge.plan_version_id = version_id
    surcharge.age_from = body.age_from
    surcharge.age_to = body.age_to
    surcharge.surcharge_percent = body.surcharge_percent

    db.add(surcharge)
    await db.commit()
    await db.refresh(surcharge)

    return AgeSurchargeDataResponse(
        data=_build_surcharge_out(surcharge),
        toast={"type": "success", "message": "Rango de edad creado."},
    )


# ─────────────────────────── AgeSurcharge: update ────────────────────────────


@router.patch("/{version_id}/age-surcharges/{surcharge_id}", response_model=AgeSurchargeDataResponse)
async def age_surcharges_update(
    product_id: int,
    version_id: int,
    surcharge_id: int,
    body: UpdateAgeSurchargeRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> AgeSurchargeDataResponse:
    """Actualiza un recargo por edad (parcial)."""
    surcharge = await _get_surcharge(product_id, version_id, surcharge_id, db)

    for field in body.model_fields_set:
        setattr(surcharge, field, getattr(body, field))

    await db.commit()
    await db.refresh(surcharge)

    return AgeSurchargeDataResponse(
        data=_build_surcharge_out(surcharge),
        toast={"type": "success", "message": "Rango de edad actualizado."},
    )


# ─────────────────────────── AgeSurcharge: destroy ───────────────────────────


@router.delete("/{version_id}/age-surcharges/{surcharge_id}", response_model=AgeSurchargeDeleteResponse)
async def age_surcharges_destroy(
    product_id: int,
    version_id: int,
    surcharge_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> AgeSurchargeDeleteResponse:
    """Elimina un recargo por edad."""
    surcharge = await _get_surcharge(product_id, version_id, surcharge_id, db)

    sid = surcharge.id
    await db.delete(surcharge)
    await db.commit()

    return AgeSurchargeDeleteResponse(id=sid, message="Rango de edad eliminado.")
