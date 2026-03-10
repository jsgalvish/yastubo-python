from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.concerns.has_directory import HasDirectory

if TYPE_CHECKING:
    from app.models.company_user import CompanyUser
    from app.models.company_commission_user import CompanyCommissionUser
    from app.models.product import Product
    from app.models.file import File


class Company(HasDirectory, SoftDeleteMixin, TimestampMixin, Base):
    """Empresa / compañía cliente del sistema."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rut: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_file_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("files.id"), nullable=True
    )
    pdf_template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("templates.id"), nullable=True
    )
    primary_color: Mapped[str | None] = mapped_column(String(10), nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String(10), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relaciones
    logo: Mapped[File | None] = relationship("File", foreign_keys=[logo_file_id])
    users: Mapped[list[CompanyUser]] = relationship("CompanyUser", back_populates="company")
    commission_users: Mapped[list[CompanyCommissionUser]] = relationship(
        "CompanyCommissionUser", back_populates="company"
    )
    products: Mapped[list[Product]] = relationship("Product", back_populates="company")
