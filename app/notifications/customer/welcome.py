"""
Notificación de bienvenida para clientes.

Equivale a App\\Notifications\\Customer\\WelcomeCustomer de PHP.
"""

from __future__ import annotations

from app.models.user import User
from app.notifications.email_service import send_email


async def send_welcome_customer(user: User, login_url: str, temp_password: str) -> None:
    """Envía email de bienvenida al nuevo cliente."""
    await send_email(
        to=user.email,
        subject="Bienvenido(a) — Acceso a tu cuenta",
        template="customer/welcome.html",
        context={
            "user": user,
            "loginUrl": login_url,
            "tempPassword": temp_password,
        },
    )
