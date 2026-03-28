"""
Notificación de restablecimiento de contraseña para clientes.

Equivale a App\\Notifications\\Customer\\ResetPasswordCustomer de PHP.
"""

from __future__ import annotations

from common.models.user import User
from common.notifications.email_service import send_email


async def send_reset_password_customer(user: User, url: str, minutes: int = 30) -> None:
    """Envía email de restablecimiento de contraseña al cliente."""
    await send_email(
        to=user.email,
        subject="Restablecer contraseña",
        template="customer/reset-password.html",
        context={
            "user": user,
            "url": url,
            "minutes": minutes,
        },
    )
