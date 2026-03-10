from __future__ import annotations

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ConfigItem(TimestampMixin, Base):
    """
    Ítem de configuración polimórfico.

    Tipos de valor (columna `type`):
      - int:     valor entero (value_int)
      - decimal: valor decimal (value_decimal)
      - text:    texto libre (value_text)
      - trans:   texto traducible JSON (value_trans)
      - date:    fecha (value_date)
      - file:    referencia a archivo (value_file_*_id)
    """

    __tablename__ = "config_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    config: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON opciones extra

    # Valores polimórficos
    value_int: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value_decimal: Mapped[float | None] = mapped_column(Numeric(15, 4), nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_trans: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON {"es":..., "en":...}
    value_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    value_file_es_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("files.id"), nullable=True
    )
    value_file_en_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("files.id"), nullable=True
    )
    value_file_plain_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("files.id"), nullable=True
    )

    def get_value(self) -> int | float | str | None:
        """Retorna el valor según el tipo."""
        if self.type == "int":
            return self.value_int
        if self.type == "decimal":
            return self.value_decimal
        if self.type == "trans":
            return self.value_trans
        if self.type == "date":
            return self.value_date
        if self.type == "file":
            return self.value_file_plain_id
        return self.value_text
