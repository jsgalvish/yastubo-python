from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    action: str
    context_json: Optional[str] = None
    target_user_id: Optional[int] = None
    created_at: str


class PaginationMeta(BaseModel):
    current_page: int
    last_page: int
    per_page: int
    total: int


class AuditLogsResponse(BaseModel):
    data: list[AuditLogOut]
    meta: PaginationMeta
