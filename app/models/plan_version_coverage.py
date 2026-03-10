from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.concerns.has_translatable_json import HasTranslatableJson

if TYPE_CHECKING:
    from app.models.plan_version import PlanVersion
    from app.models.coverage import Coverage


class PlanVersionCoverage(HasTranslatableJson, SoftDeleteMixin, TimestampMixin, Base):
    """
    Cobertura específica de una versión de plan.
    El valor se almacena en la columna que corresponda según el tipo de unidad.
    """

    __tablename__ = "plan_version_coverages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plan_version_id: Mapped[int] = mapped_column(
        ForeignKey("plan_versions.id"), nullable=False
    )
    coverage_id: Mapped[int] = mapped_column(
        ForeignKey("coverages.id"), nullable=False
    )
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value_int: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value_decimal: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON {"es":..., "en":...}
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)       # JSON {"es":..., "en":...}

    # Relaciones
    plan_version: Mapped[PlanVersion] = relationship(
        "PlanVersion", back_populates="coverages"
    )
    coverage: Mapped[Coverage] = relationship("Coverage", back_populates="plan_version_coverages")

    def get_display_value(self, locale: str = "es") -> str | None:
        """
        Retorna el valor formateado según el tipo de unidad de medida.
        Equivale al accessor getDisplayValueAttribute de PHP.
        """
        from app.models.unit_of_measure import UnitOfMeasure
        from app.support.format_service import FormatService

        if self.coverage is None or self.coverage.unit is None:
            return None

        unit = self.coverage.unit
        formatter = FormatService(locale)

        if unit.measure_type == UnitOfMeasure.TYPE_TEXT:
            return self.translate(self.value_text, locale)
        elif unit.measure_type == UnitOfMeasure.TYPE_INTEGER:
            return f"{formatter.integer(self.value_int)} {self.translate(unit.name, locale)}"
        elif unit.measure_type == UnitOfMeasure.TYPE_DECIMAL:
            return f"{formatter.decimal(self.value_decimal)} {self.translate(unit.name, locale)}"
        elif unit.measure_type == UnitOfMeasure.TYPE_NONE:
            return self.translate(unit.name, locale)
        return None
