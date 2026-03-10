from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class StaffProfile(TimestampMixin, Base):
    """
    Perfil de usuario de backoffice (staff/admin).
    Clave primaria = user_id (no autoincremental).
    """

    __tablename__ = "staff_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True, autoincrement=False
    )
    commission: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    can_issue: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Relaciones
    user: Mapped[User] = relationship("User", back_populates="staff_profile")
