from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ConfigItem(TimestampMixin, Base):
    """
    Ítem de configuración polimórfico.

    Tipos de valor:
      - int:     valor entero (value_int)
      - decimal: valor decimal (value_decimal)
      - text:    texto libre (value_text)
      - trans:   texto traducible JSON (value_text)
      - date:    fecha (value_text, ISO format)
      - file:    referencia a file_id (value_int)
    """

    __tablename__ = "config_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    configurable_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    configurable_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False)
    value_int: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value_decimal: Mapped[float | None] = mapped_column(nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def get_value(self) -> int | float | str | None:
        """Retorna el valor según el tipo."""
        if self.value_type in ("int", "file"):
            return self.value_int
        if self.value_type == "decimal":
            return self.value_decimal
        return self.value_text
