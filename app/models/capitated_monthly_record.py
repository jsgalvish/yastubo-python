from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.product import Product
    from app.models.capitated_product_insured import CapitatedProductInsured
    from app.models.capitated_contract import CapitatedContract
    from app.models.plan_version import PlanVersion
    from app.models.country import Country


class CapitatedMonthlyRecord(TimestampMixin, Base):
    """
    Registro mensual aprobado de un asegurado capitado.
    Un asegurado tiene máximo un registro por company+product+mes.
    """

    __tablename__ = "capitados_monthly_records"

    __table_args__ = (
        UniqueConstraint(
            "company_id", "product_id", "person_id", "coverage_month",
            name="capitados_monthly_records_unique"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("capitados_product_insureds.id"), nullable=False
    )
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("capitados_contracts.id"), nullable=False
    )
    coverage_month: Mapped[date] = mapped_column(Date, nullable=False)
    plan_version_id: Mapped[int] = mapped_column(
        ForeignKey("plan_versions.id"), nullable=False
    )
    load_batch_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Snapshot de persona
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sex: Mapped[str] = mapped_column(String(1), nullable=False)
    age_reported: Mapped[int | None] = mapped_column(Integer, nullable=True)
    residence_country_id: Mapped[int | None] = mapped_column(
        ForeignKey("countries.id"), nullable=True
    )
    repatriation_country_id: Mapped[int | None] = mapped_column(
        ForeignKey("countries.id"), nullable=True
    )

    # Auditoría tarifaria
    price_base: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    age_surcharge_rule_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_surcharge_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    age_surcharge_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_final: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Relaciones
    company: Mapped[Company] = relationship("Company")
    product: Mapped[Product] = relationship("Product")
    person: Mapped[CapitatedProductInsured] = relationship("CapitatedProductInsured")
    contract: Mapped[CapitatedContract] = relationship("CapitatedContract")
    plan_version: Mapped[PlanVersion] = relationship("PlanVersion")
    residence_country: Mapped[Country | None] = relationship(
        "Country", foreign_keys=[residence_country_id]
    )
    repatriation_country: Mapped[Country | None] = relationship(
        "Country", foreign_keys=[repatriation_country_id]
    )
