from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.role import Role

# Constante que identifica el modelo User en las tablas polimórficas de Spatie.
# Debe coincidir con el valor almacenado en la BD por PHP.
USER_MODEL_TYPE = "App\\Models\\User"

# ── Tablas de asociación Spatie ───────────────────────────────────────────────

role_has_permissions = Table(
    "role_has_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

model_has_roles = Table(
    "model_has_roles",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("model_type", String(255), primary_key=True),
    Column("model_id", Integer, primary_key=True),
)

model_has_permissions = Table(
    "model_has_permissions",
    Base.metadata,
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("model_type", String(255), primary_key=True),
    Column("model_id", Integer, primary_key=True),
)


# ── Modelo Permission ─────────────────────────────────────────────────────────


class Permission(TimestampMixin, Base):
    """
    Permiso del sistema.
    Equivale a Spatie\\Permission\\Models\\Permission con campo description extra.

    Tablas Spatie que maneja este módulo:
      - permissions            (esta clase)
      - role_has_permissions   (M2M roles ↔ permissions)
      - model_has_roles        (M2M users ↔ roles, polimórfico)
      - model_has_permissions  (M2M users ↔ permissions, polimórfico)
    """

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    guard_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relación con roles (vía role_has_permissions)
    roles: Mapped[list[Role]] = relationship(
        "Role",
        secondary=role_has_permissions,
        back_populates="permissions",
    )
