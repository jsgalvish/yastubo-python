from __future__ import annotations

import os
import uuid as uuid_lib

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class File(TimestampMixin, Base):
    """
    Archivo almacenado en disco o en la nube.
    Equivale a File.php con disk, path, uuid.
    """

    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid_lib.uuid4()), nullable=False, unique=True
    )
    disk: Mapped[str] = mapped_column(String(50), default="local", nullable=False)
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[int | None] = mapped_column(nullable=True)

    def url(self) -> str | None:
        """Retorna la URL pública del archivo (si es público)."""
        from app.config import settings
        if self.disk == "public":
            return f"{settings.app_url}/storage/{self.path}"
        return None

    def local_path(self) -> str:
        """Retorna la ruta absoluta local del archivo."""
        from app.config import settings
        return os.path.join(settings.app_storage_dir, self.path)
