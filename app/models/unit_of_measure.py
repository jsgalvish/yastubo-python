from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.concerns.has_translatable_json import HasTranslatableJson


class UnitOfMeasure(HasTranslatableJson, TimestampMixin, Base):
    """Unidad de medida para coberturas."""

    __tablename__ = "units_of_measure"

    TYPE_INTEGER = "integer"
    TYPE_DECIMAL = "decimal"
    TYPE_TEXT = "text"
    TYPE_NONE = "none"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)         # JSON {"es":..., "en":...}
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON {"es":..., "en":...}
    measure_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    @staticmethod
    def measure_types() -> list[str]:
        return [
            UnitOfMeasure.TYPE_INTEGER,
            UnitOfMeasure.TYPE_DECIMAL,
            UnitOfMeasure.TYPE_TEXT,
            UnitOfMeasure.TYPE_NONE,
        ]

    @property
    def name_es(self) -> str | None:
        return self.translate(self.name, "es")
