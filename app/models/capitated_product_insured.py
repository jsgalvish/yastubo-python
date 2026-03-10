from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.product import Product
    from app.models.country import Country


class CapitatedProductInsured(TimestampMixin, Base):
    """
    Asegurado de un producto capitado.
    Un asegurado es único por company + product + document_number.
    """

    __tablename__ = "capitados_product_insureds"

    __table_args__ = (
        UniqueConstraint(
            "company_id", "product_id", "document_number",
            name="capitados_insureds_company_product_document_unique"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    document_number: Mapped[str] = mapped_column(String(64), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sex: Mapped[str] = mapped_column(String(1), nullable=False)
    residence_country_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("countries.id"), nullable=True
    )
    repatriation_country_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("countries.id"), nullable=True
    )
    age_reported: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relaciones
    company: Mapped[Company] = relationship("Company")
    product: Mapped[Product] = relationship("Product")
    residence_country: Mapped[Country | None] = relationship(
        "Country", foreign_keys=[residence_country_id]
    )
    repatriation_country: Mapped[Country | None] = relationship(
        "Country", foreign_keys=[repatriation_country_id]
    )
