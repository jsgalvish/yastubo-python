"""
Gestor de la base de datos GeoIP (MMDB).

Migrado de App\\Services\\IpCountry\\GeoIpDatabaseManager.php.

NOTA: Este servicio requiere ``maxminddb`` para leer archivos MMDB.
      Verificar que este instalado: pip install maxminddb
      (No se encontro en las dependencias del proyecto al momento de la migracion.)
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import shutil
import tarfile
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Tipo del provider config (dict con claves del .env / config)
ProviderConfig = dict[str, Any]


class GeoIpDatabaseManager:
    """
    Gestiona la descarga, actualizacion y lectura del archivo MMDB
    para resolucion de IP a pais.
    """

    def __init__(self) -> None:
        self._reader: Any | None = None

    # ------------------------------------------------------------------
    # getReader
    # ------------------------------------------------------------------

    async def get_reader(self) -> Any:
        """
        Retorna un reader de maxminddb listo para consultar IPs.
        Asegura que la base este fresca antes de abrirla.
        """
        await self.ensure_fresh_database(force=False)

        if self._reader is None:
            import maxminddb

            self._reader = maxminddb.open_database(str(self._mmdb_path()))

        return self._reader

    # ------------------------------------------------------------------
    # ensureFreshDatabase
    # ------------------------------------------------------------------

    async def ensure_fresh_database(self, force: bool = False) -> None:
        """
        Descarga y actualiza la base MMDB si esta vencida o no existe.

        Parametros
        ----------
        force : bool
            Si es True, fuerza la descarga sin importar la edad del archivo.
        """
        provider = settings.ip_country_provider
        cfg = self._get_provider_config(provider)

        if not cfg:
            raise RuntimeError(f"IP Country provider [{provider}] no esta configurado.")

        storage_dir = self._storage_dir()
        storage_dir.mkdir(parents=True, exist_ok=True)

        mmdb = self._mmdb_path()
        ttl_days = int(cfg.get("ttl_days", 30))

        # Fast path
        if not force and mmdb.is_file() and not self._is_expired(mmdb, ttl_days):
            return

        # Descargar e instalar
        await self._download_and_install(provider, cfg, mmdb)

        # Reset reader
        if self._reader is not None:
            try:
                self._reader.close()
            except Exception:
                pass
            self._reader = None

    # ------------------------------------------------------------------
    # Private: download and install
    # ------------------------------------------------------------------

    async def _download_and_install(
        self, provider: str, cfg: ProviderConfig, target_mmdb: Path
    ) -> None:
        """Descarga la base MMDB segun el tipo de provider configurado."""
        tmp_dir = Path(tempfile.mkdtemp(prefix="ip_country_"))

        try:
            db_type = cfg.get("type")

            if db_type == "mmdb":
                url = cfg.get("download_url")
                if not url:
                    raise RuntimeError(f"Falta download_url para [{provider}].")

                tmp_file = tmp_dir / "db.mmdb"
                timeout = int(cfg.get("http_timeout_seconds", 60))
                await self._http_download_to(url, tmp_file, timeout)
                self._atomic_replace(tmp_file, target_mmdb)

            elif db_type == "mmdb_gz_discover":
                page_url = cfg.get("discover_page_url")
                regex = cfg.get("discover_regex")
                if not page_url or not regex:
                    raise RuntimeError(
                        f"Falta discover_page_url/discover_regex para [{provider}]."
                    )

                timeout = int(cfg.get("http_timeout_seconds", 60))

                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    resp = await client.get(page_url)
                    resp.raise_for_status()
                    html = resp.text

                m = re.search(regex, html)
                if not m:
                    raise RuntimeError(f"No se pudo descubrir URL MMDB.GZ desde {page_url}")

                gz_url = m.group(0)
                tmp_gz = tmp_dir / "db.mmdb.gz"
                tmp_mmdb = tmp_dir / "db.mmdb"

                await self._http_download_to(gz_url, tmp_gz, timeout)
                self._gunzip_to(tmp_gz, tmp_mmdb)
                self._atomic_replace(tmp_mmdb, target_mmdb)

            elif db_type == "zip_mmdb":
                token = cfg.get("token")
                if not token:
                    raise RuntimeError("IP2Location: falta IP2LOCATION_DOWNLOAD_TOKEN.")

                template = cfg.get("download_url_template")
                file_code = cfg.get("file_code")
                if not template or not file_code:
                    raise RuntimeError(
                        "IP2Location: falta download_url_template o file_code."
                    )

                url = template.replace("{token}", token).replace("{file}", file_code)
                timeout = int(cfg.get("http_timeout_seconds", 120))

                tmp_zip = tmp_dir / "db.zip"
                await self._http_download_to(url, tmp_zip, timeout)

                tmp_mmdb = tmp_dir / "db.mmdb"
                self._extract_first_mmdb_from_zip(tmp_zip, tmp_mmdb)
                self._atomic_replace(tmp_mmdb, target_mmdb)

            elif db_type == "archive_mmdb":
                url = cfg.get("download_url")
                if not url:
                    raise RuntimeError("MaxMind: falta MAXMIND_DOWNLOAD_URL.")

                timeout = int(cfg.get("http_timeout_seconds", 120))
                archive_format = cfg.get("archive_format", "zip")

                ext = "tar.gz" if archive_format == "tar.gz" else "zip"
                tmp_archive = tmp_dir / f"db.{ext}"
                await self._http_download_to(url, tmp_archive, timeout, cfg)

                tmp_mmdb = tmp_dir / "db.mmdb"

                if archive_format == "tar.gz":
                    self._extract_first_mmdb_from_tar_gz(tmp_archive, tmp_mmdb)
                else:
                    self._extract_first_mmdb_from_zip(tmp_archive, tmp_mmdb)

                self._atomic_replace(tmp_mmdb, target_mmdb)

            else:
                raise RuntimeError(
                    f"Tipo de proveedor no soportado: [{db_type}] para [{provider}]."
                )

            # Metadatos
            meta = {
                "provider": provider,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "type": db_type,
            }
            meta_path = target_mmdb.parent / "ip-country.meta.json"
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        except Exception:
            logger.error(
                "[GeoIpDatabaseManager] Error actualizando DB",
                exc_info=True,
                extra={"provider": provider},
            )
            raise
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # HTTP download
    # ------------------------------------------------------------------

    async def _http_download_to(
        self,
        url: str,
        dest: Path,
        timeout_seconds: int,
        cfg: ProviderConfig | None = None,
    ) -> None:
        """Descarga un archivo via HTTP."""
        cfg = cfg or {}
        auth = None
        if cfg.get("account_id") and cfg.get("license_key"):
            auth = httpx.BasicAuth(cfg["account_id"], cfg["license_key"])

        async with httpx.AsyncClient(
            timeout=timeout_seconds, follow_redirects=True, auth=auth
        ) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with dest.open("wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                        f.write(chunk)

        if not dest.is_file() or dest.stat().st_size < 1024:
            raise RuntimeError(f"Archivo descargado invalido o vacio: {dest}")

    # ------------------------------------------------------------------
    # Archive extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _gunzip_to(src_gz: Path, dest: Path) -> None:
        """Descomprime un archivo .gz."""
        with gzip.open(str(src_gz), "rb") as f_in, dest.open("wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

        if not dest.is_file() or dest.stat().st_size < 1024:
            raise RuntimeError(f"gunzip produjo archivo invalido: {dest}")

    @staticmethod
    def _extract_first_mmdb_from_zip(zip_path: Path, dest_mmdb: Path) -> None:
        """Extrae el primer .mmdb de un ZIP."""
        with zipfile.ZipFile(str(zip_path), "r") as zf:
            mmdb_name = None
            for name in zf.namelist():
                if name.lower().endswith(".mmdb"):
                    mmdb_name = name
                    break

            if not mmdb_name:
                raise RuntimeError("No se encontro .mmdb dentro del ZIP.")

            with zf.open(mmdb_name) as src, dest_mmdb.open("wb") as dst:
                shutil.copyfileobj(src, dst)

        if not dest_mmdb.is_file() or dest_mmdb.stat().st_size < 1024:
            raise RuntimeError(f"Extraccion ZIP produjo archivo invalido: {dest_mmdb}")

    @staticmethod
    def _extract_first_mmdb_from_tar_gz(tar_gz_path: Path, dest_mmdb: Path) -> None:
        """Extrae el primer .mmdb de un tar.gz."""
        with tarfile.open(str(tar_gz_path), "r:gz") as tf:
            mmdb_member = None
            for member in tf.getmembers():
                if member.name.lower().endswith(".mmdb"):
                    mmdb_member = member
                    break

            if not mmdb_member:
                raise RuntimeError("No se encontro .mmdb dentro del TAR.GZ.")

            extracted = tf.extractfile(mmdb_member)
            if not extracted:
                raise RuntimeError("No se pudo extraer .mmdb del TAR.GZ.")

            with dest_mmdb.open("wb") as f:
                shutil.copyfileobj(extracted, f)

        if not dest_mmdb.is_file() or dest_mmdb.stat().st_size < 1024:
            raise RuntimeError(f"Extraccion TAR.GZ produjo archivo invalido: {dest_mmdb}")

    @staticmethod
    def _atomic_replace(src: Path, dest: Path) -> None:
        """Reemplazo atomico de archivo."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp_dest = dest.with_suffix(".tmp")

        if tmp_dest.exists():
            tmp_dest.unlink()

        shutil.copy2(str(src), str(tmp_dest))

        if dest.exists():
            dest.unlink()

        tmp_dest.rename(dest)

    # ------------------------------------------------------------------
    # Config & paths
    # ------------------------------------------------------------------

    @staticmethod
    def _storage_dir() -> Path:
        """Directorio de almacenamiento para archivos GeoIP."""
        base = settings.app_storage_dir
        if base:
            return Path(base) / "geoip"
        return Path("storage") / "geoip"

    @classmethod
    def _mmdb_path(cls) -> Path:
        return cls._storage_dir() / "ip-country.mmdb"

    @staticmethod
    def _is_expired(path: Path, ttl_days: int) -> bool:
        """Determina si el archivo MMDB esta vencido."""
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return True

        age_seconds = time.time() - mtime
        return age_seconds > (ttl_days * 86400)

    @staticmethod
    def _get_provider_config(provider: str) -> ProviderConfig | None:
        """
        Retorna la configuracion del provider.

        En el proyecto Python la configuracion de providers se maneja
        a traves de variables de entorno individuales (no un dict anidado
        como en Laravel). Este metodo construye el dict equivalente.
        """
        # Configuracion minima basada en el provider conocido
        configs: dict[str, ProviderConfig] = {
            "iplocate": {
                "type": "mmdb_gz_discover",
                "discover_page_url": "https://www.iplocate.io/downloads",
                "discover_regex": r"https://[^\s\"']+\.mmdb\.gz",
                "ttl_days": 30,
                "http_timeout_seconds": 60,
            },
            "maxmind": {
                "type": "archive_mmdb",
                "archive_format": "tar.gz",
                "ttl_days": 30,
                "http_timeout_seconds": 120,
            },
        }

        return configs.get(provider)

    # ------------------------------------------------------------------
    # Diagnostics helpers
    # ------------------------------------------------------------------

    def mmdb_info(self) -> dict[str, Any]:
        """Informacion sobre el archivo MMDB para diagnosticos."""
        mmdb = self._mmdb_path()
        exists = mmdb.is_file()
        mtime = mmdb.stat().st_mtime if exists else None

        return {
            "path": str(mmdb),
            "exists": exists,
            "size_bytes": mmdb.stat().st_size if exists else None,
            "mtime": mtime,
            "age_days": round((time.time() - mtime) / 86400, 2) if mtime else None,
        }

    def mmdb_meta(self) -> dict[str, Any] | None:
        """Lee metadatos del archivo meta.json."""
        meta_path = self._storage_dir() / "ip-country.meta.json"
        if not meta_path.is_file():
            return None

        try:
            raw = meta_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None
