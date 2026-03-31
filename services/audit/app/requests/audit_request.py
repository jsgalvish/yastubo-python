from __future__ import annotations

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    action: str
    context_json: str | None = None
    target_user_id: int | None = None
    performed_by_user_id: int | None = None
    performed_by_name: str | None = None
    created_at: str


class PaginationMeta(BaseModel):
    current_page: int
    last_page: int
    per_page: int
    total: int


class AuditLogsResponse(BaseModel):
    data: list[AuditLogOut]
    meta: PaginationMeta
