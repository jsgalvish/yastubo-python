"""
CRM Controller — Zoho Integration
Endpoints para visualizar y gestionar la sincronización con Zoho CRM.
"""

from __future__ import annotations

import contextlib
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_db
from common.middleware.permission import require_permission
from common.models.user import User

router = APIRouter(prefix="/admin/crm", tags=["admin:crm"])


@router.get("/sync-log")
async def get_sync_log(
    entity_type: str = Query(default="all"),
    _current_user: User = Depends(require_permission("admin.config.read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Lista registros de sincronización con Zoho CRM."""
    query = "SELECT * FROM zoho_sync_log"
    if entity_type != "all":
        query += f" WHERE entity_type = '{entity_type}'"
    query += " ORDER BY synced_at DESC"

    result = await db.execute(text(query))
    rows = result.all()
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

    # Stats
    stats = {}
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
        text("SELECT entity_type, COUNT(*) as cnt FROM zoho_sync_log GROUP BY entity_type")
    )
    by_type = {row[0]: row[1] for row in result.all()}

    total = sum(by_type.values())

    return {
        "total_synced": total,
        "accounts": by_type.get("company", 0),
        "contacts": by_type.get("subscription", 0),
        "deals": by_type.get("deal", 0),
        "leads": by_type.get("lead", 0),
        "zoho_url": "https://crm.zoho.eu/crm/org20113056937",
    }
