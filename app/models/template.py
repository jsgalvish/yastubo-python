from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.template_version import TemplateVersion


class Template(SoftDeleteMixin, TimestampMixin, Base):
    """
    Plantilla de documento (HTML o PDF).

    Tipos:
      - TYPE_HTML: plantilla HTML (emails, documentos web)
      - TYPE_PDF:  plantilla PDF (contratos, certificados)
    """

    __tablename__ = "templates"

    TYPE_HTML = "html"
    TYPE_PDF = "pdf"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(10), default="html", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool | None] = mapped_column(default=True, nullable=True)

    # Relaciones
    versions: Mapped[list[TemplateVersion]] = relationship(
        "TemplateVersion", back_populates="template"
    )
