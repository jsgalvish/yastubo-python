from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.plan_version import PlanVersion


class PlanVersionAgeSurcharge(TimestampMixin, Base):
    """Recargo por edad aplicado a una versión de plan."""

    __tablename__ = "plan_version_age_surcharges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plan_version_id: Mapped[int] = mapped_column(
        ForeignKey("plan_versions.id"), nullable=False
    )
    age_from: Mapped[int] = mapped_column(Integer, nullable=False)
    age_to: Mapped[int] = mapped_column(Integer, nullable=False)
    surcharge_percent: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    # Relaciones
    plan_version: Mapped[PlanVersion] = relationship(
        "PlanVersion", back_populates="age_surcharges"
    )
