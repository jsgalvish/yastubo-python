from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.concerns.has_translatable_json import HasTranslatableJson

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.plan_version import PlanVersion


class Product(HasTranslatableJson, TimestampMixin, Base):
    """
    Producto de seguro.

    Tipos:
      - TYPE_PLAN_REGULAR:   plan de seguro regular
      - TYPE_PLAN_CAPITADO:  plan capitado
    """

    __tablename__ = "products"

    TYPE_PLAN_REGULAR = "plan_regular"
    TYPE_PLAN_CAPITADO = "plan_capitado"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=True
    )
    product_type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)         # JSON {"es":..., "en":...}
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON {"es":..., "en":...}
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    show_in_widget: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relaciones
    company: Mapped[Company | None] = relationship("Company", back_populates="products")
    versions: Mapped[list[PlanVersion]] = relationship(
        "PlanVersion", back_populates="product"
    )

    @property
    def name_es(self) -> str | None:
        return self.translate(self.name, "es")

    @property
    def description_es(self) -> str | None:
        return self.translate(self.description, "es")

    @staticmethod
    def types() -> list[str]:
        return [Product.TYPE_PLAN_REGULAR, Product.TYPE_PLAN_CAPITADO]
