from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.models.base import Base, TimestampMixin
from common.models.concerns.has_translatable_json import HasTranslatableJson

if TYPE_CHECKING:
    from common.models.coverage_category import CoverageCategory
    from common.models.unit_of_measure import UnitOfMeasure
    from common.models.plan_version_coverage import PlanVersionCoverage


class Coverage(HasTranslatableJson, TimestampMixin, Base):
    """Cobertura de seguro (ítem de un plan)."""

    __tablename__ = "coverages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("coverage_categories.id"), nullable=True
    )
    unit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("units_of_measure.id"), nullable=True
    )
    name: Mapped[str | None] = mapped_column(Text, nullable=True)         # JSON {"es":..., "en":...}
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON {"es":..., "en":...}
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relaciones
    category: Mapped[CoverageCategory | None] = relationship(
        "CoverageCategory", back_populates="coverages"
    )
    unit: Mapped[UnitOfMeasure | None] = relationship("UnitOfMeasure")
    plan_version_coverages: Mapped[list[PlanVersionCoverage]] = relationship(
        "PlanVersionCoverage", back_populates="coverage"
    )

    @property
    def name_es(self) -> str | None:
        return self.translate(self.name, "es")
