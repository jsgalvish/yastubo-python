from __future__ import annotations

import logging

from fastapi import Request

logger = logging.getLogger(__name__)


class Audit:
    @staticmethod
    async def log(
        action: str,
        context: dict | None = None,
        target_user_id: int | None = None,
        request: Request | None = None,
    ) -> None:
        """
        Registra un evento en audit_logs.

        TODO: completar en Step 2 (Models) cuando AuditLog esté disponible.
        """
        try:
            pass  # TODO: AuditLog.create(...)
        except Exception as e:
            logger.warning("Audit log failed: %s", e)
