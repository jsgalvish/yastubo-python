from __future__ import annotations

import json
import logging

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class Audit:
    @staticmethod
    async def log(
        action: str,
        context: dict | None = None,
        target_user_id: int | None = None,
        request: Request | None = None,
        db: AsyncSession | None = None,
    ) -> None:
        """
        Registra un evento en audit_logs.
        Si no se provee db, el log se omite silenciosamente.
        """
        if db is None:
            return

        try:
            from app.models.audit_log import AuditLog

            record = AuditLog(
                action=action,
                context_json=json.dumps(context) if context else None,
                target_user_id=target_user_id,
            )
            db.add(record)
            await db.flush()
        except Exception as e:
            logger.warning("Audit log failed: %s", e)
