from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.capitated_batch_log import CapitatedBatchLog
    from app.models.product import Product
    from app.models.plan_version import PlanVersion
    from app.models.capitated_product_insured import CapitatedProductInsured
    from app.models.capitated_contract import CapitatedContract
    from app.models.capitated_monthly_record import CapitatedMonthlyRecord
    from app.models.country import Country


class CapitatedBatchItemLog(TimestampMixin, Base):
    """
    Detalle de una fila procesada en un lote capitado.

    Resultados posibles: applied | rejected | incongruence | duplicated
    """

    __tablename__ = "capitados_batch_item_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("capitados_batch_logs.id"), nullable=False
    )

    # Ubicación en el Excel
    sheet_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Plan / versión
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"), nullable=True
    )
    plan_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_versions.id"), nullable=True
    )

    # País de residencia
    residence_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    residence_code_extracted: Mapped[str | None] = mapped_column(String(8), nullable=True)
    residence_country_id: Mapped[int | None] = mapped_column(
        ForeignKey("countries.id"), nullable=True
    )

    # País de repatriación
    repatriation_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repatriation_code_extracted: Mapped[str | None] = mapped_column(String(8), nullable=True)
    repatriation_country_id: Mapped[int | None] = mapped_column(
        ForeignKey("countries.id"), nullable=True
    )

    # Datos de persona desde el Excel
    document_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(1), nullable=True)
    age_reported: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Resultado
    result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rejection_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rejection_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Referencias a entidades resultantes
    person_id: Mapped[int | None] = mapped_column(
        ForeignKey("capitados_product_insureds.id"), nullable=True
    )
    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("capitados_contracts.id"), nullable=True
    )
    monthly_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("capitados_monthly_records.id"), nullable=True
    )
    duplicated_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("capitados_monthly_records.id"), nullable=True
    )

    # Relaciones
    batch: Mapped[CapitatedBatchLog] = relationship("CapitatedBatchLog")
    product: Mapped[Product | None] = relationship("Product")
    plan_version: Mapped[PlanVersion | None] = relationship("PlanVersion")
    person: Mapped[CapitatedProductInsured | None] = relationship(
        "CapitatedProductInsured"
    )
    contract: Mapped[CapitatedContract | None] = relationship("CapitatedContract")
    monthly_record: Mapped[CapitatedMonthlyRecord | None] = relationship(
        "CapitatedMonthlyRecord", foreign_keys=[monthly_record_id]
    )
    duplicated_record: Mapped[CapitatedMonthlyRecord | None] = relationship(
        "CapitatedMonthlyRecord", foreign_keys=[duplicated_record_id]
    )
    residence_country: Mapped[Country | None] = relationship(
        "Country", foreign_keys=[residence_country_id]
    )
    repatriation_country: Mapped[Country | None] = relationship(
        "Country", foreign_keys=[repatriation_country_id]
    )
