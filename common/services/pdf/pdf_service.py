"""
Servicio de generacion de PDF.

Usa Jinja2 para renderizar plantillas HTML y WeasyPrint para
convertir el HTML resultante a PDF con soporte completo de CSS.

Dependencias en produccion (Linux):
    apt install libpango1.0-dev libgdk-pixbuf2.0-dev libffi-dev
    pip install weasyprint jinja2

Dependencias en Windows (dev):
    Instalar GTK3 Runtime: https://github.com/nicoseddio/weasyprint-win/releases
    pip install weasyprint jinja2
"""
from __future__ import annotations

import os
import sys

# En Windows, agregar GTK3 al PATH para que WeasyPrint encuentre las DLLs
if sys.platform == "win32":
    _gtk_lib = r"C:\Program Files\GTK3-Runtime Win64\lib"
    if os.path.isdir(_gtk_lib):
        os.environ["PATH"] = _gtk_lib + os.pathsep + os.environ.get("PATH", "")
        # Python 3.8+ requires explicit DLL directory registration
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(_gtk_lib)

from jinja2 import BaseLoader, Environment


def render_template(content: str, data: dict) -> str:
    """
    Renderiza una plantilla HTML (string) con variables usando Jinja2.

    Los templates deben estar en sintaxis Jinja2 pura:
    {{ var }}, {% if %}, {% for %}, etc.
    """
    env = Environment(loader=BaseLoader(), autoescape=False)
    template = env.from_string(content)
    return template.render(**data)


def html_to_pdf(html: str, base_url: str | None = None) -> bytes:
    """Convierte HTML a PDF usando WeasyPrint."""
    from pathlib import Path
    from weasyprint import HTML

    # Siempre usar el directorio de este archivo como base para resolver imágenes
    _this_dir = Path(__file__).resolve().parent
    base_url = _this_dir.as_uri() + "/"

    doc = HTML(string=html, base_url=base_url)
    return doc.write_pdf()


async def html_to_pdf_async(html: str, base_url: str | None = None) -> bytes:
    """Wrapper async que ejecuta html_to_pdf en un thread separado."""
    import asyncio
    return await asyncio.to_thread(html_to_pdf, html, base_url)
