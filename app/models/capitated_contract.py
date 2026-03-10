from __future__ import annotations

import uuid as uuid_lib
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.product import Product
    from app.models.capitated_product_insured import CapitatedProductInsured


class CapitatedContract(TimestampMixin, Base):
    """
    Contrato de asegurado capitado.
    El UUID se genera automáticamente al crear el registro.

    Estados: active | expired | voided
    """

    __tablename__ = "capitados_contracts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("capitados_product_insureds.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    entry_age: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Carencias
    wtime_suicide_ends_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    wtime_preexisting_conditions_ends_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    wtime_accident_ends_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    terminated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hash único (agregado en migración posterior)
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)

    # Relaciones
    company: Mapped[Company] = relationship("Company")
    product: Mapped[Product] = relationship("Product")
    person: Mapped[CapitatedProductInsured] = relationship("CapitatedProductInsured")


@event.listens_for(CapitatedContract, "before_insert")
def _set_contract_hash(mapper, connection, target: CapitatedContract) -> None:
    """Genera hash UUID antes de insertar si no está definido."""
    if not target.hash:
        target.hash = str(uuid_lib.uuid4()).replace("-", "")
