from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.concerns.has_directory import HasDirectory

if TYPE_CHECKING:
    from app.models.business_unit_membership import BusinessUnitMembership
    from app.models.business_unit_commission_user import BusinessUnitCommissionUser


class BusinessUnit(HasDirectory, SoftDeleteMixin, TimestampMixin, Base):
    """
    Unidad de negocio (estructura de árbol vía parent_id).
    Equivale a BusinessUnit.php con relación parent/children recursiva.
    """

    __tablename__ = "business_units"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("business_units.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    primary_color: Mapped[str | None] = mapped_column(String(10), nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Árbol
    parent: Mapped[BusinessUnit | None] = relationship(
        "BusinessUnit", remote_side="BusinessUnit.id", back_populates="children"
    )
    children: Mapped[list[BusinessUnit]] = relationship(
        "BusinessUnit", back_populates="parent"
    )

    # Miembros y comisiones
    memberships: Mapped[list[BusinessUnitMembership]] = relationship(
        "BusinessUnitMembership", back_populates="business_unit"
    )
    commission_users: Mapped[list[BusinessUnitCommissionUser]] = relationship(
        "BusinessUnitCommissionUser", back_populates="business_unit"
    )

    def ancestor_chain(self) -> list[BusinessUnit]:
        """
        Retorna la cadena de ancestros [raíz, ..., padre, self].
        Equivale a ancestorChain() de PHP.
        """
        chain: list[BusinessUnit] = []
        node: BusinessUnit | None = self
        visited: set[int] = set()
        while node is not None:
            if node.id in visited:
                break
            visited.add(node.id)
            chain.insert(0, node)
            node = node.parent
        return chain
