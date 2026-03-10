from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.concerns.has_directory import HasDirectory

if TYPE_CHECKING:
    from app.models.staff_profile import StaffProfile
    from app.models.customer_profile import CustomerProfile
    from app.models.password_history import PasswordHistory
    from app.models.user_preference import UserPreference
    from app.models.audit_log import AuditLog
    from app.models.company_user import CompanyUser
    from app.models.business_unit_membership import BusinessUnitMembership


REALM_ADMIN = "admin"
REALM_CUSTOMER = "customer"

STATUS_ACTIVE = "active"
STATUS_SUSPENDED = "suspended"
STATUS_LOCKED = "locked"


class User(HasDirectory, SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "users"

    __table_args__ = (
        Index("users_email_realm_idx", "email", "realm"),
        Index("users_realm_status_idx", "realm", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Login / dominio
    realm: Mapped[str] = mapped_column(
        Enum("admin", "customer", name="users_realm_enum"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    force_password_change: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Identidad
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Estado y verificación
    status: Mapped[str] = mapped_column(
        Enum("active", "suspended", "locked", name="users_status_enum"),
        default="active",
        nullable=False,
        index=True,
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Preferencias y auditoría
    locale: Mapped[str] = mapped_column(String(5), default="es", nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(50), default="America/Santiago", nullable=False
    )
    ui_settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    remember_token: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relaciones
    staff_profile: Mapped[StaffProfile | None] = relationship(
        "StaffProfile", back_populates="user", uselist=False
    )
    customer_profile: Mapped[CustomerProfile | None] = relationship(
        "CustomerProfile", back_populates="user", uselist=False
    )
    password_histories: Mapped[list[PasswordHistory]] = relationship(
        "PasswordHistory", back_populates="user"
    )
    preferences: Mapped[list[UserPreference]] = relationship(
        "UserPreference", back_populates="user"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        "AuditLog", back_populates="target_user", foreign_keys="AuditLog.target_user_id"
    )
    company_memberships: Mapped[list[CompanyUser]] = relationship(
        "CompanyUser", back_populates="user"
    )
    business_unit_memberships: Mapped[list[BusinessUnitMembership]] = relationship(
        "BusinessUnitMembership", back_populates="user"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def is_admin(self) -> bool:
        return self.realm == REALM_ADMIN

    def is_customer(self) -> bool:
        return self.realm == REALM_CUSTOMER
