from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.file import File
    from app.models.user import User


class CapitatedBatchLog(TimestampMixin, Base):
    """
    Cabecera de un lote de carga de asegurados capitados.

    Estados:
      - STATUS_DRAFT:     borrador (en proceso de carga)
      - STATUS_PROCESSED: procesado exitosamente
      - STATUS_FAILED:    error en el procesamiento
    """

    __tablename__ = "capitados_batch_logs"

    STATUS_DRAFT = "draft"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    coverage_month: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="excel", nullable=False)
    source_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("files.id"), nullable=True
    )
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Contadores
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_applied: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_duplicated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_incongruences: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_plan_errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Auditoría de reglas
    is_any_month_allowed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    cutoff_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Resumen
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relaciones
    company: Mapped[Company] = relationship("Company")
    source_file: Mapped[File | None] = relationship(
        "File", foreign_keys=[source_file_id]
    )
    created_by: Mapped[User | None] = relationship(
        "User", foreign_keys=[created_by_user_id]
    )
