"""
Notificación de restablecimiento de contraseña para administradores.

Equivale a App\\Notifications\\Admin\\ResetPasswordAdmin de PHP.
"""

from __future__ import annotations

from common.models.user import User
from common.notifications.email_service import send_email


async def send_reset_password_admin(user: User, url: str, minutes: int = 30) -> None:
    """Envía email de restablecimiento de contraseña al administrador."""
    await send_email(
        to=user.email,
        subject="Restablecer contraseña (Admin)",
        template="admin/reset-password.html",
        context={
            "user": user,
            "url": url,
            "minutes": minutes,
        },
    )
