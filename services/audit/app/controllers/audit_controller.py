"""
Auditoría & Trazabilidad — Module E
Endpoints de lectura del registro inmutable de acciones.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_db
from common.middleware.permission import require_permission
from common.models.audit_log import AuditLog
from common.models.user import User
from app.requests.audit_request import AuditLogOut, AuditLogsResponse, PaginationMeta

router = APIRouter(prefix="/admin/audit", tags=["admin:audit"])

_PERMISSION = "admin.audit.read"


@router.get("", response_model=AuditLogsResponse)
async def audit_index(
    user_id: Optional[int] = Query(default=None),
    action: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> AuditLogsResponse:
    """Lista paginada del log de auditoría con filtros."""
    import math
    q = select(AuditLog).order_by(AuditLog.created_at.desc())

    if user_id is not None:
        q = q.where(AuditLog.target_user_id == user_id)
    if action:
        q = q.where(AuditLog.action.ilike(f"%{action}%"))
    if date_from:
        q = q.where(func.date(AuditLog.created_at) >= date_from)
    if date_to:
        q = q.where(func.date(AuditLog.created_at) <= date_to)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    items = list((await db.execute(q.offset((page - 1) * per_page).limit(per_page))).scalars().all())

    return AuditLogsResponse(
        data=[AuditLogOut(
            id=log.id,
            action=log.action,
            context_json=log.context_json,
            target_user_id=log.target_user_id,
            created_at=str(log.created_at),
        ) for log in items],
        meta=PaginationMeta(
            current_page=page,
            last_page=max(1, math.ceil(total / per_page)),
            per_page=per_page,
            total=total,
        ),
    )
