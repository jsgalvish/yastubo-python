from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.concerns.has_translatable_json import HasTranslatableJson

if TYPE_CHECKING:
    from app.models.zone import Zone


# Tabla de asociación country ↔ zone (many-to-many)
# Se define en zone.py


class Country(HasTranslatableJson, TimestampMixin, Base):
    """País del catálogo geográfico."""

    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON {"es":..., "en":...}
    iso2: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    iso3: Mapped[str | None] = mapped_column(String(3), nullable=True)
    continent_code: Mapped[str] = mapped_column(String(2), nullable=False)
    phone_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relaciones
    zones: Mapped[list[Zone]] = relationship(
        "Zone", secondary="country_zone", back_populates="countries"
    )

    @property
    def name_es(self) -> str | None:
        return self.translate(self.name, "es")

    @classmethod
    def find_by_iso2(cls, iso2: str) -> str:
        """Retorna el iso2 normalizado (uppercase) para búsquedas."""
        return iso2.upper()
