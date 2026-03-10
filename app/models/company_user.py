from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class CompanyUser(TimestampMixin, Base):
    """
    Tabla pivot company_user (Usuario ↔ Empresa).
    Equivale al Pivot CompanyUser de PHP.
    """

    __tablename__ = "company_user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    basic_functions: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relaciones
    company: Mapped[Company] = relationship("Company", back_populates="users")
    user: Mapped[User] = relationship("User", back_populates="company_memberships")
