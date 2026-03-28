from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from common.models.company import Company
    from common.models.user import User


class CompanyCommissionUser(TimestampMixin, Base):
    """Comisión de un usuario asociada a una empresa."""

    __tablename__ = "company_commission_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    commission: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    # Relaciones
    company: Mapped[Company] = relationship(
        "Company", back_populates="commission_users"
    )
    user: Mapped[User] = relationship("User")
