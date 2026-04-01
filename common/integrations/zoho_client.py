"""
Zoho CRM API v2 async client.

Maneja OAuth2 token refresh y operaciones CRUD sobre módulos CRM.
Si las credenciales no están configuradas opera en modo dry-run.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from common.config import settings

logger = logging.getLogger("zoho_client")


class ZohoTokenError(Exception):
    pass


class ZohoCrmClient:
    """Async HTTP client para Zoho CRM API v2."""

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._token_expiry: float = 0
        self._api_base = f"{settings.zoho_api_domain}/crm/v2"

    # ── Properties ────────────────────────────────────────────────────

    @property
    def is_configured(self) -> bool:
        return bool(
            settings.zoho_client_id
            and settings.zoho_client_secret
            and settings.zoho_refresh_token
        )

    # ── Token management ──────────────────────────────────────────────

    async def _refresh_access_token(self) -> str:
        """Obtiene un nuevo access_token usando el refresh_token."""
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                f"{settings.zoho_accounts_domain}/oauth/v2/token",
                params={
                    "grant_type": "refresh_token",
                    "client_id": settings.zoho_client_id,
                    "client_secret": settings.zoho_client_secret,
                    "refresh_token": settings.zoho_refresh_token,
                },
            )
        data = resp.json()
        if "access_token" not in data:
            raise ZohoTokenError(f"Token refresh failed: {data}")
        self._access_token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600) - 60
        logger.info("Zoho access token refreshed")
        return self._access_token

    async def _get_token(self) -> str:
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
        return await self._refresh_access_token()

    async def _headers(self) -> dict[str, str]:
        token = await self._get_token()
        return {"Authorization": f"Zoho-oauthtoken {token}"}

    # ── CRUD operations ───────────────────────────────────────────────

    async def create_record(
        self, module: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Crea un registro en un módulo. Retorna el registro creado."""
        headers = await self._headers()
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.post(
                f"{self._api_base}/{module}",
                headers=headers,
                json={"data": [data]},
            )
        body = resp.json()
        if resp.status_code not in (200, 201):
            logger.error("Zoho create %s failed: %s", module, body)
            return {"error": body, "status": resp.status_code}

        details = body.get("data", [{}])[0]
        record_id = details.get("details", {}).get("id", "")
        return {"id": record_id, "details": details, "status": "success"}

    async def update_record(
        self, module: str, record_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Actualiza un registro existente."""
        headers = await self._headers()
        data["id"] = record_id
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.put(
                f"{self._api_base}/{module}",
                headers=headers,
                json={"data": [data]},
            )
        body = resp.json()
        if resp.status_code not in (200, 201):
            logger.error("Zoho update %s/%s failed: %s", module, record_id, body)
            return {"error": body, "status": resp.status_code}
        return {"id": record_id, "status": "success"}

    async def search_records(
        self, module: str, criteria: str
    ) -> list[dict[str, Any]]:
        """Busca registros por criterio. Ej: '(Email:equals:foo@bar.com)'"""
        headers = await self._headers()
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.get(
                f"{self._api_base}/{module}/search",
                headers=headers,
                params={"criteria": criteria},
            )
        if resp.status_code == 204:
            return []
        body = resp.json()
        return body.get("data", [])

    async def upsert_record(
        self, module: str, data: dict[str, Any], duplicate_check_fields: list[str]
    ) -> dict[str, Any]:
        """Upsert: crea o actualiza basado en campos de dedup."""
        headers = await self._headers()
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.post(
                f"{self._api_base}/{module}/upsert",
                headers=headers,
                json={
                    "data": [data],
                    "duplicate_check_fields": duplicate_check_fields,
                },
            )
        body = resp.json()
        if resp.status_code not in (200, 201):
            logger.error("Zoho upsert %s failed: %s", module, body)
            return {"error": body, "status": resp.status_code}
        details = body.get("data", [{}])[0]
        record_id = details.get("details", {}).get("id", "")
        action = details.get("action", "unknown")
        return {"id": record_id, "action": action, "status": "success"}


# Singleton
zoho_client = ZohoCrmClient()
