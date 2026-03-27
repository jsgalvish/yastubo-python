"""
Servicio de renderizado de plantillas.

Combina datos de prueba de Template y TemplateVersion, y renderiza
contenido HTML usando Jinja2 (equivalente a Blade en el proyecto PHP).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException
from jinja2 import BaseLoader, Environment, TemplateSyntaxError, UndefinedError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_item import ConfigItem
from app.models.file import File as FileModel
from app.support.json_decode import JsonDecode

if TYPE_CHECKING:
    from app.models.template import Template
    from app.models.template_version import TemplateVersion


class TemplateRenderService:
    """
    Servicio que construye datos fusionados y renderiza plantillas Jinja2.

    Equivalente a App\\Services\\TemplateRenderService en PHP.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # -- Datos fusionados -----------------------------------------------------

    async def build_merged_data(
        self,
        template: Template,
        version: TemplateVersion | None = None,
    ) -> dict:
        """
        Construye el dict de datos fusionando:
          1. Branding por defecto (base)
          2. test_data_json de la plantilla
          3. test_data_json de la version (si existe, pisa keys de plantilla)

        Retorna el dict resultante listo para inyectar en el template.
        """
        original: dict = {}
        original["branding"] = await self._get_default_branding()

        base = self._decode_json_text(template.test_data_json)
        ver = self._decode_json_text(version.test_data_json) if version else {}

        # dict union: original <- base <- ver  (las keys de version pisan)
        merged = {**original, **base, **ver}
        return merged

    # -- Renderizado ----------------------------------------------------------

    def render_template(self, content: str, data: dict | None = None) -> str:
        """
        Renderiza un string de plantilla Jinja2 con las variables dadas.

        Sintaxis soportada: {{ var }}, {% if %}, {% for %}, etc.

        Raises:
            HTTPException 422 si la sintaxis del template es invalida.
            HTTPException 422 si hay variables indefinidas en el template.
        """
        if data is None:
            data = {}

        try:
            env = Environment(loader=BaseLoader(), autoescape=False)
            tpl = env.from_string(content)
            return tpl.render(**data)
        except TemplateSyntaxError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Error de sintaxis en la plantilla: {exc}",
            ) from exc
        except UndefinedError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Variable indefinida en la plantilla: {exc}",
            ) from exc

    # -- Utilidades internas --------------------------------------------------

    @staticmethod
    def _decode_json_text(json_str: str | None) -> dict:
        """
        Decodifica JSON almacenado como TEXT.

        - Si es vacio/null retorna {}.
        - Si es invalido retorna {} (fallback seguro).
        - Usa JsonDecode.get() que ya maneja BOM, strip, etc.
        """
        result = JsonDecode.get(json_str)
        # JsonDecode.get devuelve [] para null/vacio; nosotros queremos dict
        if isinstance(result, list) and len(result) == 0:
            return {}
        if isinstance(result, dict):
            return result
        return {}

    async def _get_default_branding(self) -> dict:
        """
        Carga branding por defecto desde la tabla config_items.

        Replica la logica de Company::defaultBranding() del proyecto PHP.
        """
        result = await self._db.execute(
            select(ConfigItem).where(ConfigItem.category == "company_branding")
        )
        items = result.scalars().all()

        branding: dict = {}
        for item in items:
            val = item.get_value()
            if item.token == "logo" and item.type == "file" and item.value_file_plain_id:
                file_result = await self._db.execute(
                    select(FileModel).where(FileModel.id == item.value_file_plain_id)
                )
                file_obj = file_result.scalar_one_or_none()
                branding["logo"] = file_obj.local_path() if file_obj else ""
            elif val is not None:
                token = item.token
                if token in ("text_dark", "text_light", "bg_light", "bg_dark"):
                    branding[token] = "#" + str(val).lstrip("#")
                else:
                    branding[token] = val

        return branding
