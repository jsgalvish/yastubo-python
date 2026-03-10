from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SystemSetting(TimestampMixin, Base):
    """Configuración global del sistema (clave-valor JSON)."""

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value_json: Mapped[str | None] = mapped_column(Text, nullable=True)
