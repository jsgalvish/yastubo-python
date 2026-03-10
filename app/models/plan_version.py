from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.plan_version_coverage import PlanVersionCoverage
    from app.models.plan_version_age_surcharge import PlanVersionAgeSurcharge
    from app.models.country import Country
    from app.models.zone import Zone


class PlanVersion(SoftDeleteMixin, TimestampMixin, Base):
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
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms_html: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Precios
    price_adult: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_child: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_senior: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Zona
    zone_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("zones.id"), nullable=True
    )

    # Config
    has_age_surcharge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_repatriation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relaciones
    product: Mapped[Product] = relationship("Product", back_populates="versions")
    coverages: Mapped[list[PlanVersionCoverage]] = relationship(
        "PlanVersionCoverage", back_populates="plan_version"
    )
    age_surcharges: Mapped[list[PlanVersionAgeSurcharge]] = relationship(
        "PlanVersionAgeSurcharge", back_populates="plan_version"
    )
    zone: Mapped[Zone | None] = relationship("Zone")

    def can_be_activated(self) -> bool:
        """Retorna True si la versión puede activarse (está en draft)."""
        return self.status == self.STATUS_DRAFT

    def is_active(self) -> bool:
        return self.status == self.STATUS_ACTIVE
