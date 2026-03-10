from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class CustomerProfile(SoftDeleteMixin, TimestampMixin, Base):
    """
    Perfil de usuario cliente (portal).
    Clave primaria = user_id (no autoincremental).
    """

    __tablename__ = "customer_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True, autoincrement=False
    )

    # Identificación
    doc_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    doc_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Datos personales
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Contacto
    mobile_e164: Mapped[str | None] = mapped_column(String(30), nullable=True)
    alt_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_via: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Dirección y facturación
    home_address_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_address_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Emergencia
    emergency_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_phone_e164: Mapped[str | None] = mapped_column(String(30), nullable=True)
    emergency_relation: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Misc
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)           # JSON array
    notes_internal: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relaciones
    user: Mapped[User] = relationship("User", back_populates="customer_profile")
