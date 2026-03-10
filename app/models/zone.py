from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.country import Country


# Tabla pivot country_zone (many-to-many)
country_zone = Table(
    "country_zone",
    Base.metadata,
    Column("country_id", Integer, ForeignKey("countries.id"), primary_key=True),
    Column("zone_id", Integer, ForeignKey("zones.id"), primary_key=True),
)


class Zone(TimestampMixin, Base):
    """Zona geográfica (agrupa países)."""

    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relaciones
    countries: Mapped[list[Country]] = relationship(
        "Country", secondary=country_zone, back_populates="zones"
    )
