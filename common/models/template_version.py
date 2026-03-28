from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from common.models.template import Template


class TemplateVersion(TimestampMixin, Base):
    """Versión de una plantilla de documento."""

    __tablename__ = "template_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relaciones
    template: Mapped[Template] = relationship(
        "Template", back_populates="versions", foreign_keys="[TemplateVersion.template_id]"
    )
