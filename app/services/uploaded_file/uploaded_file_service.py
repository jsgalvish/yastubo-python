"""
Servicio para almacenar, reemplazar, duplicar y eliminar archivos subidos.

Migrado de App\\Services\\UploadedFileService.php.
Usa almacenamiento local basado en settings.app_storage_dir.
"""

from __future__ import annotations

import logging
import shutil
import uuid as uuid_lib
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.file import File

logger = logging.getLogger(__name__)


def _storage_root() -> Path:
    """Retorna la raiz de almacenamiento configurada."""
    return Path(settings.app_storage_dir)


def _generate_stored_path(base_path: str, original_name: str) -> tuple[str, str]:
    """
    Genera un nombre unico para almacenar el archivo.

    Retorna (relative_path, file_uuid) donde relative_path es relativo
    al storage root.
    """
    file_uuid = str(uuid_lib.uuid4())
    ext = Path(original_name).suffix  # incluye el punto
    filename = f"{file_uuid}{ext}"
    relative_path = f"{base_path.strip('/')}/{filename}"
    return relative_path, file_uuid


class UploadedFileService:
    """
    Gestiona el ciclo de vida de archivos subidos:
    store, replace, delete, get_local_path, duplicate_file.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # store
    # ------------------------------------------------------------------

    async def store(
        self,
        uploaded_file: UploadFile,
        *,
        meta: dict | None = None,
        uploaded_by_user_id: int | None = None,
        disk: str = "local",
        base_path: str = "uploads",
    ) -> File:
        """
        Almacena un archivo subido y crea el registro en la tabla files.

        Parameters
        ----------
        uploaded_file : UploadFile
            Archivo recibido por FastAPI.
        meta : dict | None
            Metadatos opcionales (se guardan en files.meta).
        uploaded_by_user_id : int | None
            ID del usuario que sube el archivo.
        disk : str
            Nombre logico del disco (por ahora solo 'local').
        base_path : str
            Carpeta base dentro del storage (ej: 'plans/terms').
        """
        original_name = uploaded_file.filename or "file"
        relative_path, file_uuid = _generate_stored_path(base_path, original_name)

        # Escribir archivo fisicamente
        abs_path = _storage_root() / relative_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        content = await uploaded_file.read()
        abs_path.write_bytes(content)

        # Crear registro en DB
        file_record = File(
            uuid=file_uuid,
            disk=disk,
            path=relative_path,
            original_name=original_name,
            mime_type=uploaded_file.content_type,
            size=len(content),
            uploaded_by=uploaded_by_user_id,
            meta=meta,
        )

        self._db.add(file_record)
        await self._db.flush()

        return file_record

    # ------------------------------------------------------------------
    # replace
    # ------------------------------------------------------------------

    async def replace(
        self,
        file_record: File,
        uploaded_file: UploadFile,
        *,
        meta: dict | None = None,
        uploaded_by_user_id: int | None = None,
        delete_old_physical: bool = True,
        disk: str | None = None,
        base_path: str = "uploads",
    ) -> File:
        """
        Reemplaza el contenido fisico de un archivo manteniendo el mismo
        registro File (mismo id / uuid).
        """
        old_path = file_record.path

        disk = disk or file_record.disk or "local"
        original_name = uploaded_file.filename or "file"
        relative_path, _ = _generate_stored_path(base_path, original_name)

        # Guardar nuevo archivo
        abs_path = _storage_root() / relative_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        content = await uploaded_file.read()
        abs_path.write_bytes(content)

        # Borrar archivo fisico antiguo
        if delete_old_physical and old_path:
            self._safe_delete_physical(old_path)

        # Actualizar registro
        file_record.disk = disk
        file_record.path = relative_path
        file_record.original_name = original_name
        file_record.mime_type = uploaded_file.content_type
        file_record.size = len(content)
        file_record.uploaded_by = uploaded_by_user_id

        if meta is not None:
            file_record.meta = meta

        await self._db.flush()

        return file_record

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    async def delete(
        self,
        file_record: File,
        *,
        delete_physical: bool = True,
    ) -> bool:
        """
        Elimina el archivo (registro y, opcionalmente, contenido fisico).

        Retorna True si el registro fue eliminado.
        """
        if delete_physical and file_record.path:
            self._safe_delete_physical(file_record.path)

        await self._db.delete(file_record)
        await self._db.flush()

        return True

    # ------------------------------------------------------------------
    # get_local_path
    # ------------------------------------------------------------------

    def get_local_path(self, file_record: File) -> str:
        """
        Devuelve la ruta absoluta local al archivo.

        En el contexto actual solo soportamos disco local, por lo que
        simplemente construimos la ruta a partir del storage root y el path
        relativo almacenado en el registro.
        """
        return str(_storage_root() / file_record.path)

    # ------------------------------------------------------------------
    # duplicate_file
    # ------------------------------------------------------------------

    async def duplicate_file(
        self,
        source_file: File,
        *,
        meta: dict | None = None,
        uploaded_by_user_id: int | None = None,
        disk: str | None = None,
        base_path: str | None = None,
    ) -> File:
        """
        Duplica un registro File y su archivo fisico en disco.
        """
        disk = disk or source_file.disk or "local"
        source_path = source_file.path

        if not source_path:
            raise RuntimeError("No se encontro el archivo origen para duplicar.")

        abs_source = _storage_root() / source_path
        if not abs_source.exists():
            raise RuntimeError("No se encontro el archivo origen para duplicar.")

        # Directorio destino
        if base_path is None:
            base_path = str(Path(source_path).parent)

        ext = Path(source_path).suffix
        new_uuid = str(uuid_lib.uuid4())
        new_filename = f"{new_uuid}{ext}"
        new_relative_path = f"{base_path.strip('/')}/{new_filename}"

        abs_target = _storage_root() / new_relative_path
        abs_target.parent.mkdir(parents=True, exist_ok=True)

        # Copiar archivo fisico
        shutil.copy2(str(abs_source), str(abs_target))

        # Crear nuevo registro
        clone = File(
            uuid=new_uuid,
            disk=disk,
            path=new_relative_path,
            original_name=source_file.original_name,
            mime_type=source_file.mime_type,
            size=source_file.size,
            uploaded_by=uploaded_by_user_id
            if uploaded_by_user_id is not None
            else source_file.uploaded_by,
            meta=meta if meta is not None else source_file.meta,
        )

        self._db.add(clone)
        await self._db.flush()

        return clone

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_delete_physical(relative_path: str) -> None:
        """Intenta eliminar un archivo fisico sin interrumpir el flujo."""
        try:
            target = _storage_root() / relative_path
            if target.is_file():
                target.unlink()
        except OSError:
            logger.warning(
                "No se pudo eliminar el archivo fisico: %s", relative_path, exc_info=True
            )
