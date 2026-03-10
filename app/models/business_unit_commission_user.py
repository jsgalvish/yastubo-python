from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.business_unit import BusinessUnit
    from app.models.user import User


class BusinessUnitCommissionUser(TimestampMixin, Base):
    """Comisión de un usuario asociada a una unidad de negocio."""

    __tablename__ = "business_unit_commission_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_unit_id: Mapped[int] = mapped_column(
        ForeignKey("business_units.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    commission: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    # Relaciones
    business_unit: Mapped[BusinessUnit] = relationship(
        "BusinessUnit", back_populates="commission_users"
    )
    user: Mapped[User] = relationship("User")
