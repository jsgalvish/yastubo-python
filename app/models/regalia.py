from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.business_unit import BusinessUnit


class Regalia(TimestampMixin, Base):
    """
    Regalía (comisión especial) asignada a un beneficiario.

    source_type: "user" | "unit"
    source_id:   ID del origen (usuario o unidad)
    """

    __tablename__ = "regalias"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    beneficiary_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    commission: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)

    # Relaciones
    beneficiary: Mapped[User] = relationship(
        "User", foreign_keys=[beneficiary_user_id]
    )
    # origin_user y origin_unit son polimórficos; se acceden por código según source_type
