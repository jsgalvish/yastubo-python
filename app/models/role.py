from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.concerns.has_translatable_json import HasTranslatableJson


class Role(HasTranslatableJson, TimestampMixin, Base):
    """
    Rol del sistema (equivale a Spatie\\Permission\\Models\\Role extendido).

    Tablas de permisos de Spatie:
      - roles                  (esta clase)
      - permissions
      - model_has_roles
      - model_has_permissions
      - role_has_permissions
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
