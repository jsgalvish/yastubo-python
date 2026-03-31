"""
Controlador público de archivos.

Endpoints:
  GET /files/{uuid}          — descarga/visualización pública por UUID
  GET /files/temp/{file_id}  — descarga temporal con firma (signature)

Equivale a App\\Http\\Controllers\\FileController de PHP.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_db
from common.models.file import File

router = APIRouter(tags=["public:files"])

_INLINE_MIMES = {"application/pdf"}
_INLINE_PREFIXES = ("image/",)


def _should_display_inline(mime: str | None) -> bool:
    if not mime:
        return False
    mime = mime.lower()
    if mime in _INLINE_MIMES:
        return True
    return any(mime.startswith(p) for p in _INLINE_PREFIXES)


async def _get_file_by_uuid(uuid: str, db: AsyncSession) -> File:
    result = await db.execute(select(File).where(File.uuid == uuid))
    f = result.scalar_one_or_none()
    if f is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return f


def _serve_file(file: File) -> FileResponse:
    """Sirve un archivo como inline o descarga según su MIME type."""
    local_path = Path(file.local_path())

    if not local_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco.")

    filename = file.original_name or local_path.name
    mime = file.mime_type or mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"

    if _should_display_inline(mime):
        return FileResponse(
            path=str(local_path),
            media_type=mime,
            filename=filename,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    return FileResponse(
        path=str(local_path),
        media_type=mime,
        filename=filename,
    )


@router.get("/files/{uuid}")
async def show_by_uuid(uuid: str, db: AsyncSession = Depends(get_db)):
    """Descarga/visualización pública de un archivo por UUID."""
    file = await _get_file_by_uuid(uuid, db)
    return _serve_file(file)


@router.get("/files/temp/{file_id}")
async def show_temporary(
    file_id: int,
    signature: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Descarga temporal de un archivo con firma.

    NOTA: En la versión PHP se usa hasValidSignature() de Laravel.
    Aquí se implementa una verificación básica con HMAC.
    """
    import hashlib
    import hmac

    from common.config import settings

    result = await db.execute(select(File).where(File.id == file_id))
    file = result.scalar_one_or_none()
    if file is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    # Verificar firma HMAC
    expected = hmac.new(
        settings.secret_key.encode(),
        f"file-temp-{file_id}".encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Link expirado o inválido.")

    return _serve_file(file)
