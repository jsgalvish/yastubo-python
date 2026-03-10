from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.business_unit import BusinessUnit
    from app.models.user import User


class BusinessUnitMembership(TimestampMixin, Base):
    """Membresía de un usuario en una unidad de negocio."""

    __tablename__ = "memberships_business_unit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_unit_id: Mapped[int] = mapped_column(
        ForeignKey("business_units.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relaciones
    business_unit: Mapped[BusinessUnit] = relationship(
        "BusinessUnit", back_populates="memberships"
    )
    user: Mapped[User] = relationship("User", back_populates="business_unit_memberships")
