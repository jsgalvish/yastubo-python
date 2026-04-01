"""
CRM Controller — Zoho Integration
Endpoints para visualizar y gestionar la sincronización con Zoho CRM.
"""

from __future__ import annotations

import contextlib
import json
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import settings
from common.database import get_db
from common.middleware.permission import require_permission
from common.models.subscription import Subscription
from common.models.user import User
from common.models.zoho_sync_log import ZohoSyncLog
from common.services.zoho_crm_service import ZohoCrmService

router = APIRouter(prefix="/admin/crm", tags=["admin:crm"])

logger = logging.getLogger("crm_controller")


@router.get("/sync-log")
async def get_sync_log(
    entity_type: str = Query(default="all"),
    _current_user: User = Depends(require_permission("admin.config.read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Lista registros de sincronización con Zoho CRM."""
    stmt = select(ZohoSyncLog).order_by(ZohoSyncLog.synced_at.desc())
    if entity_type != "all":
        stmt = stmt.where(ZohoSyncLog.entity_type == entity_type)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    data = []
    for row in rows:
        sync_data = {}
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            sync_data = json.loads(row.sync_data) if row.sync_data else {}
        data.append(
            {
                "id": row.id,
                "entity_type": row.entity_type,
                "local_id": row.local_id,
                "zoho_module": row.zoho_module,
                "zoho_record_id": row.zoho_record_id,
                "sync_data": sync_data,
                "synced_at": str(row.synced_at) if row.synced_at else None,
            }
        )

    stats: dict[str, int] = {}
    for d in data:
        t = d["entity_type"]
        stats[t] = stats.get(t, 0) + 1

    return {"data": data, "stats": stats, "total": len(data)}


@router.get("/dashboard")
async def crm_dashboard(
    _current_user: User = Depends(require_permission("admin.config.read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dashboard CRM con métricas de sincronización."""
    result = await db.execute(
        select(ZohoSyncLog.entity_type, func.count().label("cnt")).group_by(
            ZohoSyncLog.entity_type
        )
    )
    by_type = {row[0]: row[1] for row in result.all()}
    total = sum(by_type.values())

    return {
        "total_synced": total,
        "accounts": by_type.get("company", 0),
        "contacts": by_type.get("subscription_contact", 0),
        "deals": by_type.get("deal", 0),
        "leads": by_type.get("lead", 0),
        "zoho_url": settings.zoho_org_url,
        "zoho_configured": bool(settings.zoho_client_id),
    }


@router.post("/sync-now")
async def sync_now(
    current_user: User = Depends(require_permission("admin.config.read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Fuerza sincronización de todas las suscripciones activas con Zoho CRM."""
    crm = ZohoCrmService(db)

    result = await db.execute(
        select(Subscription).where(Subscription.status == Subscription.STATUS_ACTIVE)
    )
    subscriptions = result.scalars().all()

    synced = 0
    errors = 0

    for sub in subscriptions:
        try:
            user_result = await db.execute(select(User).where(User.id == sub.user_id))
            user = user_result.scalar_one_or_none()
            if user:
                await crm.sync_subscription_to_contact_deal(sub, user)
                synced += 1
        except Exception:
            logger.exception("sync_now failed for subscription %s", sub.id)
            errors += 1

    return {
        "synced": synced,
        "errors": errors,
        "total": len(subscriptions),
    }
