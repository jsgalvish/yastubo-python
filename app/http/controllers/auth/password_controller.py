from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.http.middleware.auth import get_admin_user, get_customer_user
from app.http.requests.auth.password_request import (
    ChangePasswordRequest,
    ForcePasswordRequest,
    PasswordCheckRequest,
    PasswordCheckResponse,
)
from app.models.user import User
from app.services.auth_service import AuthService
from app.support.password_history_service import PasswordHistoryService
from app.support.password_policy import PasswordPolicy

router = APIRouter(tags=["auth"])

_policy = PasswordPolicy()


@router.get("/password/policy")
async def password_policy() -> dict:
    """
    Retorna la política de contraseñas para el frontend.
    Endpoint público — no requiere autenticación.
    Equivale a PasswordController::policy() de PHP.
    """
    return _policy.for_frontend()


@router.post("/password/check", response_model=PasswordCheckResponse)
async def password_check(body: PasswordCheckRequest) -> PasswordCheckResponse:
    """
    Valida una contraseña en tiempo real (sin autenticación).
    Equivale a PasswordController::check() de PHP.
    """
    context = {
        "first_name":   body.first_name or "",
        "last_name":    body.last_name or "",
        "display_name": body.display_name or "",
        "email":        body.email or "",
    }
    errors = _policy.validate(body.password, context)
    return PasswordCheckResponse(valid=len(errors) == 0, errors=errors)


async def _change_password(
    user: User,
    body: ChangePasswordRequest | ForcePasswordRequest,
    db: AsyncSession,
) -> dict:
    """Lógica compartida de cambio de contraseña."""
    # 1) Verificar contraseña actual
    if not AuthService.verify_password(body.current_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"current_password": "La contraseña actual no es válida."},
        )

    # 2) Validar política
    context = {
        "first_name":   user.first_name,
        "last_name":    user.last_name,
        "display_name": user.display_name or "",
        "email":        user.email,
    }
    errors = _policy.validate(body.password, context)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"password": errors},
        )

    # 3) Verificar historial
    history_svc = PasswordHistoryService(db)
    if await history_svc.reused(user, body.password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"password": "No puedes reutilizar una contraseña reciente."},
        )

    # 4) Guardar nueva contraseña
    old_hash = user.password
    user.password = AuthService.hash_password(body.password)
    user.force_password_change = False

    # 5) Recordar hash anterior en historial
    await history_svc.remember(user, old_hash)

    db.add(user)
    await db.commit()

    return {"status": "Contraseña actualizada."}


@router.post("/admin/password/change")
async def admin_change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cambio de contraseña propio — admin."""
    return await _change_password(user, body, db)


@router.post("/customer/password/change")
async def customer_change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_customer_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cambio de contraseña propio — customer."""
    return await _change_password(user, body, db)


@router.post("/admin/password/force")
async def admin_force_password(
    body: ForcePasswordRequest,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Cambio forzado de contraseña tras login — admin.
    Equivale a ForcedPasswordController::update() de PHP.
    """
    return await _change_password(user, body, db)


@router.post("/customer/password/force")
async def customer_force_password(
    body: ForcePasswordRequest,
    user: User = Depends(get_customer_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cambio forzado de contraseña tras login — customer."""
    return await _change_password(user, body, db)


# ── Forgot / Reset Password ─────────────────────────────────────────────────


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    email: EmailStr
    password: str
    password_confirmation: str


async def _forgot_password(realm: str, body: ForgotPasswordRequest, db: AsyncSession) -> dict:
    """
    Genera un token de reset y lo almacena en remember_token.
    En producción, envía el email con el link de reset.

    Equivale a PasswordController::emailLink() de PHP.
    """
    result = await db.execute(
        select(User).where(
            User.email == body.email,
            User.realm == realm,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    # Siempre retornamos éxito para no revelar si el email existe
    if not user:
        return {"status": "Si el correo existe, recibirás un enlace de restablecimiento."}

    # Generar token y guardar
    token = secrets.token_urlsafe(48)
    user.remember_token = token
    await db.commit()

    # Enviar email (best effort, no bloquea)
    try:
        if realm == "admin":
            from app.config import settings
            from app.notifications.admin.reset_password import send_reset_password_admin

            url = f"{settings.app_url}/admin/reset-password/{token}?email={user.email}"
            await send_reset_password_admin(user, url, minutes=30)
        else:
            from app.config import settings
            from app.notifications.customer.reset_password import send_reset_password_customer

            url = f"{settings.app_url}/customer/reset-password/{token}?email={user.email}"
            await send_reset_password_customer(user, url, minutes=30)
    except Exception:
        pass  # No falla si el email no se puede enviar

    return {"status": "Si el correo existe, recibirás un enlace de restablecimiento."}


async def _reset_password(realm: str, body: ResetPasswordRequest, db: AsyncSession) -> dict:
    """
    Restablece la contraseña usando el token.

    Equivale a PasswordController::reset() de PHP.
    """
    if body.password != body.password_confirmation:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"password_confirmation": "Las contraseñas no coinciden."},
        )

    result = await db.execute(
        select(User).where(
            User.email == body.email,
            User.realm == realm,
            User.remember_token == body.token,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Token inválido o expirado.",
        )

    # Validar política
    context = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "display_name": user.display_name or "",
        "email": user.email,
    }
    errors = _policy.validate(body.password, context)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"password": errors},
        )

    # Actualizar contraseña
    user.password = AuthService.hash_password(body.password)
    user.remember_token = None
    user.force_password_change = False
    await db.commit()

    return {"status": "Contraseña restablecida correctamente."}


@router.post("/admin/forgot-password")
async def admin_forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Solicitar restablecimiento de contraseña — admin."""
    return await _forgot_password("admin", body, db)


@router.post("/admin/reset-password")
async def admin_reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Restablecer contraseña con token — admin."""
    return await _reset_password("admin", body, db)


@router.post("/customer/forgot-password")
async def customer_forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Solicitar restablecimiento de contraseña — customer."""
    return await _forgot_password("customer", body, db)


@router.post("/customer/reset-password")
async def customer_reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Restablecer contraseña con token — customer."""
    return await _reset_password("customer", body, db)


@router.post("/customer/locale")
async def customer_locale(
    body: dict,
    user: User = Depends(get_customer_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cambiar locale del customer autenticado."""
    locale = body.get("locale", "")
    if locale not in ("es", "en", "pt"):
        raise HTTPException(status_code=422, detail="Locale no soportado.")
    user.locale = locale
    await db.commit()
    return {"ok": True, "locale": locale}
