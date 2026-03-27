"""
Notificación de bienvenida para administradores.

Equivale a App\\Notifications\\Admin\\WelcomeAdmin de PHP.
"""

from __future__ import annotations

from app.models.user import User
from app.notifications.email_service import send_email


async def send_welcome_admin(user: User, login_url: str, temp_password: str) -> None:
    """Envía email de bienvenida al nuevo administrador."""
    await send_email(
        to=user.email,
        subject="Bienvenido(a) — Acceso Administrativo",
        template="admin/welcome.html",
        context={
            "user": user,
            "loginUrl": login_url,
            "tempPassword": temp_password,
        },
    )
