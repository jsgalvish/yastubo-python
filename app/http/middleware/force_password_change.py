"""
Dependency que bloquea el acceso si el usuario debe cambiar su contraseña.

Equivale a App\Http\Middleware\ForcePasswordChange de PHP.
En PHP, redirige a la ruta password.force.edit; aquí retorna 403 con un
código específico que el frontend interpreta para redirigir.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError

from app.http.middleware.auth import get_current_user
from app.models.user import User

# Rutas que están permitidas incluso cuando force_password_change = True.
# El frontend llama a estas para cambiar la contraseña o cerrar sesión.
_ALLOWED_PATHS = {
    "/admin/password/force",
    "/customer/password/force",
    "/admin/password/change",
    "/customer/password/change",
    "/admin/logout",
    "/customer/logout",
    "/password/policy",
    "/password/check",
}


async def ensure_password_not_forced(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    """
    Dependency que verifica que el usuario no tenga pendiente un cambio
    de contraseña forzado.

    Si force_password_change es True y la ruta actual no es una de las
    permitidas, retorna HTTP 403 con detail especial.

    Uso:
        user: User = Depends(ensure_password_not_forced)
    """
    if not user.force_password_change:
        return user

    # Permitir ciertas rutas aun con force_password_change activo
    path = request.url.path.rstrip("/")
    if path in _ALLOWED_PATHS:
        return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "FORCE_PASSWORD_CHANGE",
            "message": "Debe cambiar su contraseña antes de continuar.",
        },
    )
