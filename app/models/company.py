from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.concerns.has_directory import HasDirectory

if TYPE_CHECKING:
    from app.models.company_user import CompanyUser
    from app.models.company_commission_user import CompanyCommissionUser
    from app.models.product import Product
    from app.models.user import User


class Company(HasDirectory, TimestampMixin, Base):
    """Empresa / compañía cliente del sistema."""

    __tablename__ = "companies"

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_ARCHIVED = "archived"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pdf_template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("templates.id"), nullable=True
    )
    commission_beneficiary_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    # Branding
    branding_logo_file_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("files.id"), nullable=True
    )
    branding_bg_light: Mapped[str | None] = mapped_column(String(20), nullable=True)
    branding_bg_dark: Mapped[str | None] = mapped_column(String(20), nullable=True)
    branding_text_light: Mapped[str | None] = mapped_column(String(20), nullable=True)
    branding_text_dark: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relaciones
    users: Mapped[list[CompanyUser]] = relationship("CompanyUser", back_populates="company")
    commission_users: Mapped[list[CompanyCommissionUser]] = relationship(
        "CompanyCommissionUser", back_populates="company"
    )
    products: Mapped[list[Product]] = relationship("Product", back_populates="company")
    commission_beneficiary: Mapped[User | None] = relationship(
        "User", foreign_keys=[commission_beneficiary_user_id]
    )
