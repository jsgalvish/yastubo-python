from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserPreference(TimestampMixin, Base):
    """Preferencias individuales de usuario (clave-valor JSON)."""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relaciones
    user: Mapped[User] = relationship("User", back_populates="preferences")
