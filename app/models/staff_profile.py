from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class StaffProfile(SoftDeleteMixin, TimestampMixin, Base):
    """
    Perfil de usuario de backoffice (staff/admin).
    Clave primaria = user_id (no autoincremental).
    """

    __tablename__ = "staff_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True, autoincrement=False
    )
    work_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    notes_admin: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Comisiones
    commission_regular_first_year_pct: Mapped[float | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    commission_regular_renewal_pct: Mapped[float | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    commission_capitados_pct: Mapped[float | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )

    # Relaciones
    user: Mapped[User] = relationship("User", back_populates="staff_profile")
