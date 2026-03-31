"""
Controlador de plantillas y versiones (admin).
Equivale a TemplateController.php + TemplateVersionController.php.

Endpoints Template:
  GET    /admin/templates                                → index
  POST   /admin/templates                                → store
  GET    /admin/templates/{id}                           → show
  PATCH  /admin/templates/{id}/basic                     → updateBasic
  PATCH  /admin/templates/{id}/test-data                 → updateTestData
  DELETE /admin/templates/{id}                           → destroy
  POST   /admin/templates/{id}/clone                     → clone

Endpoints Version:
  POST   /admin/templates/{id}/versions                  → storeVersion
  GET    /admin/templates/{id}/versions/{vid}             → showVersion
  PATCH  /admin/templates/{id}/versions/{vid}/basic       → updateVersionBasic
  PATCH  /admin/templates/{id}/versions/{vid}/test-data   → updateVersionTestData
  POST   /admin/templates/{id}/versions/{vid}/activate    → activate
  POST   /admin/templates/{id}/versions/{vid}/deactivate  → deactivate
  POST   /admin/templates/{id}/versions/{vid}/clone       → cloneVersion
  DELETE /admin/templates/{id}/versions/{vid}             → destroyVersion
  GET    /admin/templates/{id}/versions/{vid}/pdf         → previewVersionPdf
  GET    /admin/templates/{id}/active/pdf                 → previewActivePdf

Permiso: admin.templates.edit
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.requests.template_request import (
    StoreTemplateRequest,
    StoreVersionRequest,
    TemplateDataResponse,
    TemplateIndexResponse,
    TemplateOut,
    TemplateShowResponse,
    UpdateTemplateBasicRequest,
    UpdateTestDataRequest,
    UpdateVersionBasicRequest,
    VersionDataResponse,
    VersionOut,
)
from common.database import get_db
from common.middleware.permission import require_permission
from common.models.template import Template
from common.models.template_version import TemplateVersion
from common.models.user import User

router = APIRouter(prefix="/admin/templates", tags=["admin:templates"])

_PERMISSION = "admin.templates.edit"


# ─────────────────────────── Helpers ─────────────────────────────────────────


def _template_out(t: Template) -> TemplateOut:
    return TemplateOut(
        id=t.id,
        name=t.name,
        slug=t.slug,
        type=t.type,
        test_data_json=t.test_data_json,
        active_template_version_id=t.active_template_version_id,
    )


def _version_out(v: TemplateVersion) -> VersionOut:
    return VersionOut(
        id=v.id,
        template_id=v.template_id,
        name=v.name,
        content=v.content,
        test_data_json=v.test_data_json,
    )


async def _get_template(tid: int, db: AsyncSession) -> Template:
    r = await db.execute(select(Template).where(Template.id == tid, Template.deleted_at.is_(None)))
    t = r.scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada.")
    return t


async def _get_version(tid: int, vid: int, db: AsyncSession) -> TemplateVersion:
    r = await db.execute(
        select(TemplateVersion).where(
            TemplateVersion.id == vid,
            TemplateVersion.template_id == tid,
        )
    )
    v = r.scalar_one_or_none()
    if v is None:
        raise HTTPException(status_code=404, detail="Versión no encontrada.")
    return v


def _validate_json(raw: str | None) -> str | None:
    """Valida JSON y retorna None si vacío."""
    if not raw or not raw.strip():
        return None
    try:
        json.loads(raw)
        return raw
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=422, detail="JSON inválido.")


def _make_unique_slug(base: str, db_slugs: set[str]) -> str:
    """Genera un slug único para clone."""
    for _ in range(20):
        candidate = f"{base}-copia-{secrets.token_hex(3)}"
        if candidate not in db_slugs:
            return candidate
    return f"{base}-copia-{secrets.token_hex(6)}"


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATES
# ═════════════════════════════════════════════════════════════════════════════


@router.get("", response_model=TemplateIndexResponse)
async def index(
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> TemplateIndexResponse:
    """Lista todas las plantillas activas."""
    r = await db.execute(
        select(Template).where(Template.deleted_at.is_(None)).order_by(Template.name)
    )
    return TemplateIndexResponse(data=[_template_out(t) for t in r.scalars().all()])


@router.post("", response_model=TemplateDataResponse, status_code=201)
async def store(
    body: StoreTemplateRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> TemplateDataResponse:
    """Crea una nueva plantilla."""
    # Validar slug único
    existing = await db.execute(
        select(Template).where(Template.slug == body.slug, Template.deleted_at.is_(None))
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="El slug ya existe.")

    t = Template()
    t.name = body.name
    t.slug = body.slug
    t.type = body.type

    db.add(t)
    await db.commit()
    await db.refresh(t)

    return TemplateDataResponse(data={"template": _template_out(t).model_dump()})


@router.get("/{template_id}", response_model=TemplateShowResponse)
async def show(
    template_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> TemplateShowResponse:
    """Detalle de plantilla con todas sus versiones."""
    t = await _get_template(template_id, db)

    versions_r = await db.execute(
        select(TemplateVersion)
        .where(TemplateVersion.template_id == template_id)
        .order_by(TemplateVersion.id)
    )

    return TemplateShowResponse(
        data={
            "template": _template_out(t).model_dump(),
            "versions": [_version_out(v).model_dump() for v in versions_r.scalars().all()],
        }
    )


@router.patch("/{template_id}/basic", response_model=dict)
async def update_basic(
    template_id: int,
    body: UpdateTemplateBasicRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Actualiza nombre y slug de una plantilla."""
    t = await _get_template(template_id, db)

    # Validar slug único (excluyendo la actual)
    clash = await db.execute(
        select(Template).where(
            Template.slug == body.slug,
            Template.id != template_id,
            Template.deleted_at.is_(None),
        )
    )
    if clash.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="El slug ya existe.")

    t.name = body.name
    t.slug = body.slug
    await db.commit()

    return {"toast": {"type": "success", "message": "Plantilla actualizada."}}


@router.patch("/{template_id}/test-data", response_model=dict)
async def update_test_data(
    template_id: int,
    body: UpdateTestDataRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Actualiza el JSON de datos de prueba."""
    t = await _get_template(template_id, db)
    t.test_data_json = _validate_json(body.test_data_json)
    await db.commit()
    return {"toast": {"type": "success", "message": "Datos de prueba actualizados."}}


@router.delete("/{template_id}", response_model=dict)
async def destroy(
    template_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Soft-delete de una plantilla."""
    t = await _get_template(template_id, db)
    from datetime import datetime

    t.deleted_at = datetime.now(UTC)
    await db.commit()
    return {"toast": {"type": "success", "message": "Plantilla eliminada."}}


@router.post("/{template_id}/clone", response_model=TemplateDataResponse, status_code=201)
async def clone(
    template_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> TemplateDataResponse:
    """Clona una plantilla con su versión activa."""
    source = await _get_template(template_id, db)

    # Obtener slugs existentes para generar uno único
    slugs_r = await db.execute(select(Template.slug).where(Template.deleted_at.is_(None)))
    existing_slugs = {row[0] for row in slugs_r.all()}

    new_slug = _make_unique_slug(source.slug, existing_slugs)

    clone_t = Template()
    clone_t.name = source.name
    clone_t.slug = new_slug
    clone_t.type = source.type
    clone_t.test_data_json = source.test_data_json

    db.add(clone_t)
    await db.flush()

    clone_t.name = f"{source.name} (Copia) #{clone_t.id}"

    # Clonar versión activa si existe
    if source.active_template_version_id:
        src_v_r = await db.execute(
            select(TemplateVersion).where(TemplateVersion.id == source.active_template_version_id)
        )
        src_v = src_v_r.scalar_one_or_none()
        if src_v:
            clone_v = TemplateVersion()
            clone_v.template_id = clone_t.id
            clone_v.name = src_v.name
            clone_v.content = src_v.content
            clone_v.test_data_json = src_v.test_data_json
            db.add(clone_v)
            await db.flush()
            clone_v.name = f"Version #{clone_v.id}"
            clone_t.active_template_version_id = clone_v.id

    await db.commit()
    await db.refresh(clone_t)

    return TemplateDataResponse(data={"template": _template_out(clone_t).model_dump()})


# ═════════════════════════════════════════════════════════════════════════════
# VERSIONS
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/{template_id}/versions", response_model=VersionDataResponse, status_code=201)
async def store_version(
    template_id: int,
    body: StoreVersionRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> VersionDataResponse:
    """Crea una nueva versión."""
    await _get_template(template_id, db)

    v = TemplateVersion()
    v.template_id = template_id
    v.name = ""
    v.content = body.content

    db.add(v)
    await db.flush()
    v.name = f"Version #{v.id}"
    await db.commit()
    await db.refresh(v)

    return VersionDataResponse(data={"version": _version_out(v).model_dump()})


@router.get("/{template_id}/versions/{version_id}", response_model=VersionDataResponse)
async def show_version(
    template_id: int,
    version_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> VersionDataResponse:
    """Detalle de una versión."""
    v = await _get_version(template_id, version_id, db)
    return VersionDataResponse(data={"version": _version_out(v).model_dump()})


@router.patch("/{template_id}/versions/{version_id}/basic", response_model=dict)
async def update_version_basic(
    template_id: int,
    version_id: int,
    body: UpdateVersionBasicRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Actualiza nombre y contenido de una versión."""
    v = await _get_version(template_id, version_id, db)
    v.name = body.name
    v.content = body.content
    await db.commit()
    return {"toast": {"type": "success", "message": "Versión actualizada."}}


@router.patch("/{template_id}/versions/{version_id}/test-data", response_model=dict)
async def update_version_test_data(
    template_id: int,
    version_id: int,
    body: UpdateTestDataRequest,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Actualiza JSON de datos de prueba de una versión."""
    v = await _get_version(template_id, version_id, db)
    v.test_data_json = _validate_json(body.test_data_json)
    await db.commit()
    return {"toast": {"type": "success", "message": "Datos de prueba actualizados."}}


@router.post("/{template_id}/versions/{version_id}/activate", response_model=dict)
async def activate(
    template_id: int,
    version_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Activa una versión (la hace la versión principal de la plantilla)."""
    t = await _get_template(template_id, db)
    await _get_version(template_id, version_id, db)

    t.active_template_version_id = version_id
    await db.commit()

    return {"toast": {"type": "success", "message": "Versión activada."}}


@router.post("/{template_id}/versions/{version_id}/deactivate", response_model=dict)
async def deactivate(
    template_id: int,
    version_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Desactiva una versión."""
    t = await _get_template(template_id, db)
    await _get_version(template_id, version_id, db)

    if t.active_template_version_id != version_id:
        raise HTTPException(status_code=422, detail="La versión no es la activa.")

    t.active_template_version_id = None
    await db.commit()

    return {"toast": {"type": "success", "message": "Versión desactivada."}}


@router.post(
    "/{template_id}/versions/{version_id}/clone",
    response_model=VersionDataResponse,
    status_code=201,
)
async def clone_version(
    template_id: int,
    version_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> VersionDataResponse:
    """Clona una versión."""
    source = await _get_version(template_id, version_id, db)

    clone_v = TemplateVersion()
    clone_v.template_id = template_id
    clone_v.name = ""
    clone_v.content = source.content
    clone_v.test_data_json = source.test_data_json

    db.add(clone_v)
    await db.flush()
    clone_v.name = f"Version #{clone_v.id}"
    await db.commit()
    await db.refresh(clone_v)

    return VersionDataResponse(data={"version": _version_out(clone_v).model_dump()})


@router.delete("/{template_id}/versions/{version_id}", response_model=dict)
async def destroy_version(
    template_id: int,
    version_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Elimina una versión (no puede ser la activa)."""
    t = await _get_template(template_id, db)
    v = await _get_version(template_id, version_id, db)

    if t.active_template_version_id == version_id:
        raise HTTPException(status_code=422, detail="No se puede eliminar una versión activa.")

    await db.delete(v)
    await db.commit()

    return {"toast": {"type": "success", "message": "Versión eliminada."}}


# ═════════════════════════════════════════════════════════════════════════════
# PDF PREVIEW
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/{template_id}/versions/{version_id}/pdf")
async def preview_version_pdf(
    template_id: int,
    version_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Genera PDF de preview de una versión específica."""
    t = await _get_template(template_id, db)
    v = await _get_version(template_id, version_id, db)

    from common.services.pdf.pdf_service import html_to_pdf_async
    from common.services.template_render.template_render_service import TemplateRenderService

    render_service = TemplateRenderService(db)
    data = await render_service.build_merged_data(t, v)
    html = render_service.render_template(v.content, data)
    binary = await html_to_pdf_async(html)

    return Response(content=binary, media_type="application/pdf")


@router.get("/{template_id}/active/pdf")
async def preview_active_pdf(
    template_id: int,
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Genera PDF de preview de la versión activa de la plantilla."""
    t = await _get_template(template_id, db)

    if not t.active_template_version_id:
        raise HTTPException(status_code=404, detail="No hay versión activa.")

    v = await _get_version(template_id, t.active_template_version_id, db)

    from common.services.pdf.pdf_service import html_to_pdf_async
    from common.services.template_render.template_render_service import TemplateRenderService

    render_service = TemplateRenderService(db)
    data = await render_service.build_merged_data(t, v)
    html = render_service.render_template(v.content, data)
    binary = await html_to_pdf_async(html)

    return Response(content=binary, media_type="application/pdf")
