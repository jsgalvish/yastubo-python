"""Modelo ZohoSyncLog — registro de sincronización con Zoho CRM."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from common.models.base import Base


class ZohoSyncLog(Base):
    __tablename__ = "zoho_sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    local_id: Mapped[int] = mapped_column(Integer, nullable=False)
    zoho_module: Mapped[str] = mapped_column(String(100), nullable=False)
    zoho_record_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sync_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )
