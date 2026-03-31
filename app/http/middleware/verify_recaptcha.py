r"""
Dependency para verificar tokens de Google reCAPTCHA v3.

Equivale a App\Http\Middleware\VerifyRecaptcha de PHP.
Se usa como dependency en endpoints de login / forgot-password.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)

_GOOGLE_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


async def verify_recaptcha(request: Request) -> None:
    """
    Dependency que verifica el token reCAPTCHA del request.

    El token se espera en el body JSON como "recaptcha_token" o en el
    header "X-Recaptcha-Token".

    Si la verificación falla, lanza HTTP 422.

    Uso:
        @router.post("/login", dependencies=[Depends(verify_recaptcha)])
        async def login(...): ...

    Nota: Si RECAPTCHA_SECRET no está configurado, la verificación se salta
    (útil para desarrollo/testing).
    """
    secret = getattr(settings, "recaptcha_secret", "")
    if not secret:
        # Sin secret configurado, no verificar (desarrollo)
        return

    # Obtener token del body o header
    token: str | None = None

    # Intentar desde header primero
    token = request.headers.get("X-Recaptcha-Token")

    # Si no está en header, intentar desde body
    if not token:
        try:
            body = await request.json()
            token = body.get("recaptcha_token")
        except Exception:
            pass

    if not token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Token reCAPTCHA requerido.",
        )

    # Verificar con Google
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                _GOOGLE_VERIFY_URL,
                data={"secret": secret, "response": token},
            )
            result: dict[str, Any] = resp.json()
    except Exception as exc:
        logger.error("Error verificando reCAPTCHA: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se pudo verificar reCAPTCHA.",
        )

    if not result.get("success"):
        logger.warning(
            "reCAPTCHA falló: errors=%s",
            result.get("error-codes", []),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Verificación reCAPTCHA inválida.",
        )
