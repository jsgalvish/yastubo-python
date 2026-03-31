"""
Servicio base de envío de emails.

Usa aiosmtplib para envío async. Renderiza templates Jinja2.
En desarrollo (sin SMTP configurado), loguea el email en vez de enviarlo.
"""

from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from common.config import settings

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "views" / "emails"

_jinja_env: Environment | None = None


def _get_jinja_env() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
    return _jinja_env


async def send_email(
    to: str,
    subject: str,
    template: str,
    context: dict[str, Any] | None = None,
    from_addr: str | None = None,
) -> None:
    """
    Envía un email renderizando un template Jinja2.

    Args:
        to: dirección del destinatario
        subject: asunto del email
        template: nombre del template (ruta relativa desde resources/views/emails/)
        context: variables para el template
        from_addr: dirección del remitente (usa settings si no se especifica)
    """
    context = context or {}
    context.setdefault("app_url", getattr(settings, "app_url", ""))
    sender = from_addr or getattr(settings, "smtp_from", "noreply@gfa.com")

    # Renderizar template
    try:
        env = _get_jinja_env()
        tpl = env.get_template(template)
        html_body = tpl.render(**context)
    except Exception:
        logger.exception("Error renderizando template de email: %s", template)
        # Si no existe el template, crear body básico
        html_body = f"<p>{subject}</p><pre>{context}</pre>"

    # Construir mensaje
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Enviar
    smtp_host = getattr(settings, "smtp_host", "")
    smtp_port = getattr(settings, "smtp_port", 587)

    if not smtp_host:
        logger.info(
            "[EMAIL-DEV] Sin SMTP configurado. Email no enviado.\n"
            "  To: %s\n  Subject: %s\n  Template: %s",
            to,
            subject,
            template,
        )
        return

    try:
        import aiosmtplib

        smtp_user = getattr(settings, "smtp_user", "")
        smtp_password = getattr(settings, "smtp_password", "")

        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user or None,
            password=smtp_password or None,
            use_tls=smtp_port == 465,
            start_tls=smtp_port == 587,
        )
        logger.info("Email enviado a %s: %s", to, subject)
    except ImportError:
        logger.warning(
            "aiosmtplib no instalado. Email no enviado. To: %s, Subject: %s",
            to,
            subject,
        )
    except Exception:
        logger.exception("Error enviando email a %s", to)
