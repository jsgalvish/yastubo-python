from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.concerns.has_translatable_json import HasTranslatableJson

if TYPE_CHECKING:
    from app.models.coverage import Coverage


class CoverageCategory(HasTranslatableJson, TimestampMixin, Base):
    """Categoría de coberturas."""

    __tablename__ = "coverage_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)         # JSON {"es":..., "en":...}
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON {"es":..., "en":...}
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relaciones
    coverages: Mapped[list[Coverage]] = relationship(
        "Coverage", back_populates="category", order_by="Coverage.sort_order"
    )

    @property
    def name_es(self) -> str | None:
        return self.translate(self.name, "es")
