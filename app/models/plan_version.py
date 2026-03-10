from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.plan_version_coverage import PlanVersionCoverage
    from app.models.plan_version_age_surcharge import PlanVersionAgeSurcharge
    from app.models.country import Country
    from app.models.zone import Zone


class PlanVersion(TimestampMixin, Base):
    """
    Versión de un plan de seguro.

    Estados:
      - STATUS_DRAFT:    borrador (editable)
      - STATUS_ACTIVE:   activo (publicado)
      - STATUS_INACTIVE: inactivo (archivado)
    """

    __tablename__ = "plan_versions"

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    terms_html: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Precios
    public_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    cost_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_1: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_2: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_3: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_4: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Edad
    max_entry_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_renewal_age: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Tiempos de espera (días)
    wtime_preexisting_conditions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wtime_accident: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wtime_suicide: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Archivos de términos
    terms_file_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("files.id"), nullable=True
    )
    terms_file_es_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("files.id"), nullable=True
    )
    terms_file_en_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("files.id"), nullable=True
    )

    # Zona / País
    zone_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("zones.id"), nullable=True
    )
    country_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("countries.id"), nullable=True
    )

    # Relaciones
    product: Mapped[Product] = relationship("Product", back_populates="versions")
    coverages: Mapped[list[PlanVersionCoverage]] = relationship(
        "PlanVersionCoverage", back_populates="plan_version"
    )
    age_surcharges: Mapped[list[PlanVersionAgeSurcharge]] = relationship(
        "PlanVersionAgeSurcharge", back_populates="plan_version"
    )
    zone: Mapped[Zone | None] = relationship("Zone")
    country: Mapped[Country | None] = relationship("Country")

    def can_be_activated(self) -> bool:
        """Retorna True si la versión puede activarse (está en draft)."""
        return self.status == self.STATUS_DRAFT

    def is_active(self) -> bool:
        return self.status == self.STATUS_ACTIVE
