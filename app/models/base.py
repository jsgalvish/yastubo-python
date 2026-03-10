from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Clase base para todos los modelos SQLAlchemy."""
    pass


class TimestampMixin:
    """Agrega created_at y updated_at automáticos."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SoftDeleteMixin:
    """Agrega soporte de borrado suave (deleted_at)."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
