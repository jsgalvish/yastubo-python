from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.concerns.has_translatable_json import HasTranslatableJson

if TYPE_CHECKING:
    from app.models.permission import Permission


class Role(HasTranslatableJson, TimestampMixin, Base):
    """
    Rol del sistema (equivale a Spatie\\Permission\\Models\\Role extendido).

    Campos extra respecto a Spatie base:
      - scope  — 'system' o 'unit'
      - level  — jerarquía (0 = más importante)
      - label  — JSON traducible {"es": ..., "en": ...}
    """

    __tablename__ = "roles"

    SCOPE_SYSTEM = "system"
    SCOPE_UNIT = "unit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    guard_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(20), nullable=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON {"es":..., "en":...}

    # Relación con permisos (vía role_has_permissions)
    permissions: Mapped[list[Permission]] = relationship(
        "Permission",
        secondary="role_has_permissions",
        back_populates="roles",
    )

    def is_scope(self, scope: str) -> bool:
        return self.scope == scope

    @property
    def role_name(self) -> str:
        """
        Nombre de rol "bonito":
        - Usa label traducido si existe.
        - Si no, convierte name: "." → " - ", "_" → " ", luego Title Case.
        """
        label = self.translate(self.label) if self.label else None
        if label and label.strip():
            return label.strip()

        name = self.name or ""
        if not name:
            return ""

        normalized = name.replace(".", " - ").replace("_", " ")
        normalized = " ".join(normalized.split())
        return normalized.title()
