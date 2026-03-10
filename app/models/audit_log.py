from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(Base):
    """
    Registro de auditoría de eventos del sistema.
    Sin timestamps automáticos (solo created_at manual).
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    context_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relaciones
    target_user: Mapped[User | None] = relationship(
        "User", back_populates="audit_logs", foreign_keys=[target_user_id]
    )
