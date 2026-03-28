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


@router.get("/actions", response_model=list[str])
async def audit_actions(
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Lista de acciones distintas registradas en audit_logs."""
    rows = (await db.execute(
        select(AuditLog.action).distinct().order_by(AuditLog.action)
    )).scalars().all()
    return list(rows)


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

    # Collect performed_by_user_ids to resolve names in one query
    performer_ids = list({log.performed_by_user_id for log in items if log.performed_by_user_id})
    performer_names: dict[int, str] = {}
    if performer_ids:
        user_rows = list((await db.execute(
            select(User.id, User.first_name, User.last_name).where(User.id.in_(performer_ids))
        )).all())
        for row in user_rows:
            full_name = f"{row.first_name} {row.last_name or ''}".strip()
            performer_names[row.id] = full_name

    return AuditLogsResponse(
        data=[AuditLogOut(
            id=log.id,
            action=log.action,
            context_json=log.context_json,
            target_user_id=log.target_user_id,
            performed_by_user_id=log.performed_by_user_id,
            performed_by_name=performer_names.get(log.performed_by_user_id) if log.performed_by_user_id else None,
            created_at=str(log.created_at),
        ) for log in items],
        meta=PaginationMeta(
            current_page=page,
            last_page=max(1, math.ceil(total / per_page)),
            per_page=per_page,
            total=total,
        ),
    )
