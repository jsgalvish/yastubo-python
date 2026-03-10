from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class CustomerProfile(TimestampMixin, Base):
    """
    Perfil de usuario cliente (portal).
    Clave primaria = user_id (no autoincremental).
    """

    __tablename__ = "customer_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True, autoincrement=False
    )
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relaciones
    user: Mapped[User] = relationship("User", back_populates="customer_profile")
