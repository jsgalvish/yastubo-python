"""
Controlador de idioma/locale.

Endpoints:
  POST /admin/locale  — cambiar locale del usuario autenticado

Equivale a App\\Http\\Controllers\\LocaleController de PHP.
Permiso: ninguno especial (cualquier usuario autenticado).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.http.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter(tags=["admin:locale"])

_SUPPORTED_LOCALES = ("es", "en", "pt")


class UpdateLocaleRequest(BaseModel):
    locale: str


@router.post("/admin/locale")
async def update_locale(
    body: UpdateLocaleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cambia el locale del usuario autenticado."""
    if body.locale not in _SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=422,
            detail=f"Locale no soportado. Opciones: {', '.join(_SUPPORTED_LOCALES)}",
        )

    user.locale = body.locale
    await db.commit()

    return {"ok": True, "locale": body.locale}
