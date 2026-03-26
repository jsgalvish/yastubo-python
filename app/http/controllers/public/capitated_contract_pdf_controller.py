"""
Controlador publico para generacion de PDF de contratos capitados.

Equivale a CapitatedContractController::showPdfByUuid() en PHP.

Endpoint:
  GET /capitated/contracts/{uuid}/pdf  -> genera y retorna PDF del contrato

No requiere autenticacion (acceso publico por UUID).
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.capitated_contract import CapitatedContract
from app.models.capitated_monthly_record import CapitatedMonthlyRecord
from app.models.company import Company
from app.models.config_item import ConfigItem
from app.models.coverage import Coverage
from app.models.coverage_category import CoverageCategory
from app.models.file import File as FileModel
from app.models.plan_version import PlanVersion
from app.models.plan_version_coverage import PlanVersionCoverage
from app.models.template import Template
from app.models.template_version import TemplateVersion
from app.services.pdf.pdf_service import html_to_pdf_async, render_template

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/capitated/contracts",
    tags=["public:capitated-pdf"],
)


# ─────────────────────────── Helpers ─────────────────────────────────────────


def _build_coverage_categories(plan_version: PlanVersion, locale: str = "es") -> list[dict]:
    """
    Construye la estructura de categorias de cobertura agrupadas.
    Equivale a PlanVersionController::buildCoverageCategories() en PHP.
    """
    categories: dict[int, dict] = {}

    # Sort coverages by sort_order
    sorted_coverages = sorted(
        plan_version.coverages,
        key=lambda pvc: (pvc.sort_order or 0),
    )

    for pivot in sorted_coverages:
        coverage = pivot.coverage
        if coverage is None:
            continue

        category = coverage.category
        if category is None:
            continue

        cat_id = category.id

        if cat_id not in categories:
            categories[cat_id] = {
                "id": cat_id,
                "sort_order": category.sort_order or 0,
                "name": _translate(category.name, locale),
                "description": _translate(category.description, locale),
                "coverages": [],
            }

        unit = coverage.unit

        # Extract notes_t for coverage notes
        notes_t = _translate(pivot.notes, locale) if pivot.notes else None

        categories[cat_id]["coverages"].append({
            "id": pivot.id,
            "plan_version_id": pivot.plan_version_id,
            "coverage_id": pivot.coverage_id,
            "sort_order": pivot.sort_order,
            "value_int": pivot.value_int,
            "value_decimal": float(pivot.value_decimal) if pivot.value_decimal is not None else None,
            "value_text": pivot.value_text,
            "notes": pivot.notes,
            "notes_t": notes_t,
            "display_value": pivot.get_display_value(locale),
            "coverage_name": _translate(coverage.name, locale),
            "coverage_description": _translate(coverage.description, locale),
            "unit_name": _translate(unit.name, locale) if unit else None,
            "unit_measure_type": unit.measure_type if unit else None,
        })

    # Sort categories by sort_order and return as list
    return sorted(categories.values(), key=lambda c: c["sort_order"])


async def _get_branding(company: Company, db: AsyncSession) -> dict:
    """
    Construye el dict de branding de la empresa.
    Equivale a Company::branding() en PHP.
    """
    # Start with defaults from config_items
    defaults = await _get_default_branding(db)

    branding = {
        "text_dark": defaults.get("text_dark", "#000000"),
        "text_light": defaults.get("text_light", "#FFFFFF"),
        "bg_light": defaults.get("bg_light", "#FFFFFF"),
        "bg_dark": defaults.get("bg_dark", "#000000"),
        "logo": defaults.get("logo", ""),
    }

    # Override with company values if set
    if company.branding_text_dark:
        branding["text_dark"] = "#" + company.branding_text_dark.lstrip("#")
    if company.branding_text_light:
        branding["text_light"] = "#" + company.branding_text_light.lstrip("#")
    if company.branding_bg_light:
        branding["bg_light"] = "#" + company.branding_bg_light.lstrip("#")
    if company.branding_bg_dark:
        branding["bg_dark"] = "#" + company.branding_bg_dark.lstrip("#")

    # Company logo
    if company.branding_logo_file_id:
        result = await db.execute(
            select(FileModel).where(FileModel.id == company.branding_logo_file_id)
        )
        logo_file = result.scalar_one_or_none()
        if logo_file:
            branding["logo"] = logo_file.local_path()

    return branding


async def _get_default_branding(db: AsyncSession) -> dict:
    """Load default branding from config_items table."""
    result = await db.execute(
        select(ConfigItem).where(ConfigItem.category == "company_branding")
    )
    items = result.scalars().all()

    defaults: dict = {}
    for item in items:
        val = item.get_value()
        if item.token == "logo" and item.type == "file" and item.value_file_plain_id:
            # Resolve file path
            file_result = await db.execute(
                select(FileModel).where(FileModel.id == item.value_file_plain_id)
            )
            file_obj = file_result.scalar_one_or_none()
            defaults["logo"] = file_obj.local_path() if file_obj else ""
        elif val is not None:
            token = item.token
            if token in ("text_dark", "text_light", "bg_light", "bg_dark"):
                defaults[token] = "#" + str(val).lstrip("#")
            else:
                defaults[token] = val

    return defaults


async def _get_template_content(company: Company, db: AsyncSession) -> str:
    """
    Obtiene el contenido de la plantilla PDF activa de la empresa.
    Fallback a la plantilla con slug 'principal'.
    """
    template = None

    # Try company's PDF template
    if company.pdf_template_id:
        result = await db.execute(
            select(Template).where(Template.id == company.pdf_template_id)
        )
        template = result.scalar_one_or_none()

    # Fallback: template with slug 'principal'
    if template is None:
        result = await db.execute(
            select(Template).where(Template.slug == "principal")
        )
        template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(status_code=500, detail="Plantilla PDF no encontrada.")

    # Get active template version
    if template.active_template_version_id is None:
        raise HTTPException(status_code=500, detail="No hay version activa de la plantilla.")

    result = await db.execute(
        select(TemplateVersion).where(
            TemplateVersion.id == template.active_template_version_id,
        )
    )
    version = result.scalar_one_or_none()

    if version is None or not version.content:
        raise HTTPException(status_code=500, detail="Contenido de plantilla vacio.")

    return version.content


def _translate(data, locale: str = "es") -> str | None:
    """Helper to translate JSON translatable fields."""
    if data is None:
        return None
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            return data
    if isinstance(data, dict):
        return data.get(locale) or data.get("es") or next(iter(data.values()), None)
    return str(data)


# ─────────────────────────── Endpoint ────────────────────────────────────────


@router.get("/{uuid}/pdf")
async def show_pdf_by_uuid(
    uuid: str,
    debug: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Genera y retorna el PDF de un contrato capitado por UUID.

    Query params opcionales:
      ?debug=html  -> retorna el HTML renderizado (sin PDF)
      ?debug=data  -> retorna el dict de datos como JSON
    """
    # 1. Load contract by UUID
    result = await db.execute(
        select(CapitatedContract)
        .where(
            CapitatedContract.uuid == uuid,
            CapitatedContract.status.in_(["active", "expired"]),
        )
        .options(
            selectinload(CapitatedContract.person),
            selectinload(CapitatedContract.product),
            selectinload(CapitatedContract.company),
        )
    )
    contract = result.scalar_one_or_none()

    if contract is None:
        raise HTTPException(status_code=404, detail="Contrato no encontrado.")

    # 2. Get last monthly record
    mr_result = await db.execute(
        select(CapitatedMonthlyRecord)
        .where(CapitatedMonthlyRecord.contract_id == contract.id)
        .options(
            selectinload(CapitatedMonthlyRecord.residence_country),
            selectinload(CapitatedMonthlyRecord.repatriation_country),
            selectinload(CapitatedMonthlyRecord.plan_version).selectinload(
                PlanVersion.coverages
            ).selectinload(PlanVersionCoverage.coverage).selectinload(Coverage.unit),
            selectinload(CapitatedMonthlyRecord.plan_version).selectinload(
                PlanVersion.coverages
            ).selectinload(PlanVersionCoverage.coverage).selectinload(Coverage.category),
            selectinload(CapitatedMonthlyRecord.plan_version).selectinload(
                PlanVersion.product
            ),
        )
        .order_by(
            CapitatedMonthlyRecord.coverage_month.desc(),
            CapitatedMonthlyRecord.id.desc(),
        )
        .limit(1)
    )
    last_monthly_record = mr_result.scalar_one_or_none()

    if last_monthly_record is None:
        raise HTTPException(status_code=404, detail="Registros mensuales no encontrado.")

    # 3. Get related entities
    company = contract.company
    plan_version = last_monthly_record.plan_version
    product = plan_version.product
    person = contract.person

    # 4. Build coverage categories
    coverage_categories = _build_coverage_categories(plan_version)

    # 5. Build contract data dict
    short_code = company.short_code or "YTB"
    contract_id_str = f"{short_code}-{contract.id:05d}"

    residence_name = _translate(
        last_monthly_record.residence_country.name
    ) if last_monthly_record.residence_country else ""

    repatriation_name = _translate(
        last_monthly_record.repatriation_country.name
    ) if last_monthly_record.repatriation_country else ""

    entry_date_str = contract.entry_date.strftime("%d/%m/%Y") if contract.entry_date else ""
    valid_until_str = contract.valid_until.strftime("%d/%m/%Y") if contract.valid_until else ""
    emision_str = contract.created_at.strftime("%d/%m/%Y %H:%M") if contract.created_at else ""

    data = {
        "product": {
            "id": product.id,
            "name": _translate(product.name),
            "description": _translate(product.description),
        },
        "planVersion": {
            "id": plan_version.id,
            "name": plan_version.name,
            "terms_html": _translate(plan_version.terms_html) or "",
        },
        "coverageCategories": coverage_categories,
        "contrato": {
            "id": contract_id_str,
            "full_name": person.full_name,
            "age": f"{person.age_reported} años" if person.age_reported else "",
            "fecha_nacimiento": None,
            "repatriation": repatriation_name,
            "residence": residence_name,
            "document": person.document_number,
            "date_start": entry_date_str,
            "date_end": valid_until_str,
            "emision": emision_str,
            "prefix": short_code,
            "emitido_por": company.name,
            "codigo_plan": f"{product.id}v{plan_version.id}",
            "renovacion": last_monthly_record.id,
        },
    }

    # 6. Branding
    branding = await _get_branding(company, db)
    data["branding"] = branding

    # 7. Debug modes
    if debug == "data":
        return JSONResponse(content=data)

    # 8. Get template
    template_content = await _get_template_content(company, db)

    # 9. Render HTML
    html = render_template(template_content, data)

    if debug == "html":
        return Response(content=html, media_type="text/html; charset=utf-8")

    # 10. Generate PDF
    try:
        from pathlib import Path
        base_path = Path(__file__).resolve().parent.parent.parent / "services" / "pdf"
        base_url = base_path.as_uri() + "/"
        pdf_bytes = await html_to_pdf_async(html, base_url=base_url)
    except Exception as exc:
        logger.exception("Error generando PDF para contrato uuid=%s", uuid)
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {exc}") from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="contrato-{contract_id_str}.pdf"',
        },
    )
