from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt_lib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.password_policy import PASSWORD_POLICY

logger = logging.getLogger(__name__)


def _bcrypt_verify(plain: str, hashed: str) -> bool:
    """Verifica password bcrypt. Soporta prefijo $2y$ de PHP y $2b$ de Python."""
    hashed_bytes = hashed.encode("utf-8")
    if hashed_bytes.startswith(b"$2y$"):
        hashed_bytes = b"$2b$" + hashed_bytes[4:]
    return _bcrypt_lib.checkpw(plain.encode("utf-8"), hashed_bytes)


class PasswordHistoryService:
    """
    Servicio de historial de contraseñas.
    Equivale a App\\Support\\PasswordHistoryService de PHP.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def reused(self, user: object, plain: str) -> bool:
        """
        Verifica si la contraseña fue usada recientemente.

        Comprueba:
          1. Que no sea igual a la contraseña actual.
          2. Que no coincida con las últimas N del historial.
        """
        from app.models.password_history import PasswordHistory

        cfg = PASSWORD_POLICY.get("history", {})
        if not cfg.get("enabled"):
            return False

        # 1) Verificar contra contraseña actual
        current_hash: str = getattr(user, "password", "") or ""
        if current_hash and _bcrypt_verify(plain, current_hash):
            return True

        limit: int = int(cfg.get("remember_last", 0))
        if limit <= 0:
            return False

        # 2) Verificar últimas N contraseñas previas
        result = await self._db.execute(
            select(PasswordHistory)
            .where(PasswordHistory.user_id == user.id)  # type: ignore[attr-defined]
            .order_by(PasswordHistory.created_at.desc())
            .limit(limit)
        )
        for record in result.scalars().all():
            if _bcrypt_verify(plain, record.password_hash):
                return True

        return False

    async def remember(self, user: object, old_hash: str | None) -> None:
        """
        Guarda el hash anterior en el historial y purga entradas antiguas.
        """
        from app.models.password_history import PasswordHistory

        cfg = PASSWORD_POLICY.get("history", {})
        if not cfg.get("enabled"):
            return

        if not old_hash:
            return

        # Guardar hash anterior
        record = PasswordHistory(
            user_id=user.id,  # type: ignore[attr-defined]
            password_hash=old_hash,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(record)
        await self._db.flush()

        # Purgar por cantidad (mantener últimas N)
        limit: int = int(cfg.get("remember_last", 0))
        if limit > 0:
            result = await self._db.execute(
                select(PasswordHistory)
                .where(PasswordHistory.user_id == user.id)  # type: ignore[attr-defined]
                .order_by(PasswordHistory.created_at.desc())
                .offset(limit)
            )
            for old in result.scalars().all():
                await self._db.delete(old)

        # Purgar por antigüedad (opcional)
        days: int = int(cfg.get("retention_days", 0))
        if days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            result = await self._db.execute(
                select(PasswordHistory).where(
                    PasswordHistory.user_id == user.id,  # type: ignore[attr-defined]
                    PasswordHistory.created_at < cutoff,
                )
            )
            for old in result.scalars().all():
                await self._db.delete(old)
