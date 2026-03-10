from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
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
from app.support.password_policy import PasswordPolicy
from app.support.password_history_service import PasswordHistoryService

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
