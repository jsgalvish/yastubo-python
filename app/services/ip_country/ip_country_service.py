"""
Servicio de resolucion de pais por IP.

Migrado de App\\Services\\IpCountry\\IpCountryService.php.

Usa maxminddb (via GeoIpDatabaseManager) para resolver IPs a ISO2
y luego buscar el Country en la base de datos.

NOTA: Requiere ``maxminddb`` instalado: pip install maxminddb
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import re
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.country import Country
from app.services.ip_country.geoip_database_manager import GeoIpDatabaseManager

logger = logging.getLogger(__name__)

# Singleton del manager (se comparte entre requests)
_db_manager = GeoIpDatabaseManager()

# Cache simple en memoria (ip -> iso2). En produccion se podria
# reemplazar por un cache Redis; por ahora replica el comportamiento
# de Cache::remember del PHP.
_ip_cache: dict[str, str | None] = {}


class IpCountryService:
    """
    Resuelve el pais de un request a partir de la IP del cliente.

    Metodos principales:
      - resolve_country() -> Country | None
      - resolve_iso2()    -> str | None
      - resolve_iso2_by_ip() -> str | None
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._manager = _db_manager

    # ------------------------------------------------------------------
    # resolve_country
    # ------------------------------------------------------------------

    async def resolve_country(self, request: Request, only_active: bool = True) -> Country | None:
        """
        Resuelve el Country del request segun IP -> ISO2.
        Si no se puede resolver, usa el fallback ISO2 configurado.
        """
        ip = self._get_client_ip(request)

        iso2: str | None = None

        if ip and self._is_valid_public_ip(ip):
            iso2 = await self.resolve_iso2_by_ip(ip)

        if not iso2:
            iso2 = self._fallback_iso2()

        if not iso2:
            return None

        iso2 = iso2.upper()

        stmt = select(Country).where(Country.iso2 == iso2)
        if only_active:
            stmt = stmt.where(Country.is_active == True)  # noqa: E712

        r = await self._db.execute(stmt)
        return r.scalar_one_or_none()

    # ------------------------------------------------------------------
    # resolve_iso2
    # ------------------------------------------------------------------

    async def resolve_iso2(self, request: Request) -> str | None:
        """Resuelve el ISO2 del request."""
        ip = self._get_client_ip(request)

        if not ip or not self._is_valid_public_ip(ip):
            return self._fallback_iso2()

        result = await self.resolve_iso2_by_ip(ip)
        return result or self._fallback_iso2()

    # ------------------------------------------------------------------
    # resolve_iso2_by_ip
    # ------------------------------------------------------------------

    async def resolve_iso2_by_ip(self, ip: str) -> str | None:
        """Resuelve ISO2 por IP usando MMDB (con auto-descarga/refresh)."""
        ip = ip.strip()

        if not self._is_valid_ip(ip):
            return None

        # Cache en memoria
        cache_key = "ip_country:iso2:" + hashlib.sha1(ip.encode()).hexdigest()
        if cache_key in _ip_cache:
            return _ip_cache[cache_key]

        try:
            reader = await self._manager.get_reader()
            data = reader.get(ip)

            if not isinstance(data, dict):
                _ip_cache[cache_key] = None
                return None

            # MaxMind-like: country.iso_code
            iso2 = _deep_get(data, "country", "iso_code")

            # IPLocate-like: country_code
            if not iso2:
                iso2 = data.get("country_code")

            if iso2:
                iso2 = str(iso2).upper()
            else:
                iso2 = None

            _ip_cache[cache_key] = iso2 or None
            return iso2 or None

        except Exception:
            logger.debug("Error resolviendo IP %s", ip, exc_info=True)
            _ip_cache[cache_key] = None
            return None

    # ------------------------------------------------------------------
    # force_update_database
    # ------------------------------------------------------------------

    async def force_update_database(self) -> None:
        """Fuerza la actualizacion de la base MMDB."""
        await self._manager.ensure_fresh_database(force=True)

    # ------------------------------------------------------------------
    # resolve_effective_ip (dev/testing)
    # ------------------------------------------------------------------

    def resolve_effective_ip(self, request: Request) -> str | None:
        """Retorna la IP efectiva segun configuracion (solo para pruebas/dev)."""
        return self._get_client_ip(request)

    # ------------------------------------------------------------------
    # diagnostics (dev/testing)
    # ------------------------------------------------------------------

    async def diagnostics(self, request: Request) -> dict[str, Any]:
        """Payload completo para diagnosticos."""
        refresh_param = request.query_params.get("refresh", "").lower()
        refresh_requested = refresh_param in ("1", "true")
        refresh_result: str | None = None

        if refresh_requested:
            try:
                await self.force_update_database()
                refresh_result = "OK: base actualizada/descargada."
            except Exception as e:
                refresh_result = "ERROR: " + str(e)

        remote_addr = request.client.host if request.client else None
        request_ip = remote_addr

        effective_ip: str | None = None
        iso2: str | None = None
        error: str | None = None

        try:
            effective_ip = self._get_client_ip(request)
            if effective_ip:
                iso2 = await self.resolve_iso2_by_ip(effective_ip)
        except Exception as e:
            error = str(e)

        country_active = await self.resolve_country(request, only_active=True)

        country_any = None
        if iso2:
            r = await self._db.execute(select(Country).where(Country.iso2 == iso2.upper()))
            country_any = r.scalar_one_or_none()

        return {
            "provider": settings.ip_country_provider,
            "fallback_iso2": settings.ip_country_fallback_iso2,
            "refresh_requested": refresh_requested,
            "refresh_result": refresh_result,
            "remote_addr": remote_addr,
            "request_ip": request_ip,
            "effective_ip": effective_ip,
            "iso2": iso2,
            "error": error,
            "country_active": _country_dict(country_active),
            "country_any": _country_dict(country_any),
            "mmdb": self._manager.mmdb_info(),
            "meta": self._manager.mmdb_meta(),
        }

    # ------------------------------------------------------------------
    # IP detection (private)
    # ------------------------------------------------------------------

    def _get_client_ip(self, request: Request) -> str | None:
        """
        Determina la IP del cliente segun configuracion.

        En FastAPI, request.client.host da la IP directa. Para headers
        de proxy (X-Forwarded-For, CF-Connecting-IP), se leen los headers.
        """
        remote_addr = request.client.host if request.client else None

        # Intentar header X-Forwarded-For si existe
        xff = request.headers.get("x-forwarded-for")
        if xff:
            ip = self._extract_xff_ip(xff)
            if ip:
                return ip

        # CF-Connecting-IP (CloudFlare)
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            ip = self._extract_single_header_ip(cf_ip)
            if ip:
                return ip

        return remote_addr

    @staticmethod
    def _extract_single_header_ip(value: str | None) -> str | None:
        """Extrae una IP valida de un header con valor unico."""
        if not value or not isinstance(value, str):
            return None

        value = value.strip()

        # Si viene lista accidentalmente, tomar primer elemento
        if "," in value:
            value = value.split(",")[0].strip()

        return value if _is_valid_ip(value) else None

    @staticmethod
    def _extract_xff_ip(value: str | None) -> str | None:
        """Extrae la primera IP valida del header X-Forwarded-For."""
        if not value or not isinstance(value, str):
            return None

        parts = [p.strip() for p in value.split(",") if p.strip()]
        if not parts:
            return None

        # Por defecto tomamos la primera (leftmost = client original)
        candidate = parts[0]
        return candidate if _is_valid_ip(candidate) else None

    @staticmethod
    def _is_valid_public_ip(ip: str | None) -> bool:
        """Verifica que la IP sea publica (no privada ni reservada)."""
        if not ip:
            return False
        try:
            addr = ipaddress.ip_address(ip)
            return addr.is_global
        except ValueError:
            return False

    @staticmethod
    def _is_valid_ip(ip: str | None) -> bool:
        """Verifica que el string sea una IP valida."""
        if not ip:
            return False
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    @staticmethod
    def _fallback_iso2() -> str | None:
        """Retorna el ISO2 fallback configurado en .env."""
        iso2 = settings.ip_country_fallback_iso2
        if not iso2 or not isinstance(iso2, str):
            return None

        iso2 = iso2.strip().upper()

        # ISO2 debe ser exactamente 2 letras
        if re.match(r"^[A-Z]{2}$", iso2):
            return iso2
        return None


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _deep_get(data: dict, *keys: str) -> Any:
    """Acceso seguro a dicts anidados."""
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)  # type: ignore[assignment]
        if data is None:
            return None
    return data


def _is_valid_ip(ip: str) -> bool:
    """Verifica IP valida a nivel de modulo."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def _country_dict(country: Country | None) -> dict[str, Any] | None:
    """Serializa un Country a dict para diagnosticos."""
    if not country:
        return None
    return {
        "id": country.id,
        "iso2": country.iso2,
        "iso3": country.iso3,
    }
