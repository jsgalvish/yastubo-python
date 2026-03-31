"""
Servicio de configuración.

Migrado de App\\Services\\Config\\Config.php (Laravel).
Provee acceso cacheado a ítems de configuración agrupados por categoría.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_item import ConfigItem

# Claves esperadas para branding_web con valor por defecto None.
_BRANDING_WEB_KEYS = (
    "favicon",
    "favicon_claro",
    "logo_header",
    "logo_email",
    "logo_invertido",
    "imagen_login",
    "texto_bienvenida",
)


class ConfigService:
    """
    Equivale a App\\Services\\Config\\Config de PHP.

    Cada instancia recibe una AsyncSession y opera contra la tabla
    ``config_items``.  No mantiene caché estático entre requests porque
    en FastAPI cada request tiene su propia sesión; el caché se mantiene
    dentro del ciclo de vida de la instancia.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._branding_web: dict[str, int | float | str | None] | None = None

    async def get_branding_web(self) -> dict[str, int | float | str | None]:
        """
        Retorna el diccionario de branding web.

        Equivalente a ``Config::getBrandingWeb()`` en PHP:
        - Inicializa las claves conocidas con ``None``.
        - Sobreescribe con los valores almacenados en
          ``config_items`` donde ``category = 'branding_web'``.
        """
        if self._branding_web is not None:
            return self._branding_web

        # Valores por defecto
        branding: dict[str, int | float | str | None] = dict.fromkeys(_BRANDING_WEB_KEYS)

        # Buscar ítems de la categoría
        result = await self._db.execute(
            select(ConfigItem).where(ConfigItem.category == "branding_web")
        )
        items = result.scalars().all()

        for item in items:
            branding[item.token] = item.get_value()

        self._branding_web = branding
        return self._branding_web

    async def search_by_category(
        self, category: str
    ) -> dict[str, int | float | str | None]:
        """
        Retorna un diccionario ``{token: valor}`` para todos los
        ConfigItem de la categoría indicada.

        Equivale a ``ConfigItem::searchByCategory($cat)`` en PHP.
        """
        result = await self._db.execute(
            select(ConfigItem).where(ConfigItem.category == category)
        )
        items = result.scalars().all()
        return {item.token: item.get_value() for item in items}

    async def get_by_token(self, token: str) -> int | float | str | None:
        """Retorna el valor de un ítem de configuración por su token."""
        result = await self._db.execute(
            select(ConfigItem).where(ConfigItem.token == token)
        )
        item = result.scalar_one_or_none()
        if item is None:
            return None
        return item.get_value()
