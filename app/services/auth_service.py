from __future__ import annotations

from datetime import datetime, timezone

import bcrypt as _bcrypt_lib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


def _bcrypt_verify(plain: str, hashed: str) -> bool:
    """Verifica password bcrypt. Soporta prefijo $2y$ de PHP y $2b$ de Python."""
    hashed_bytes = hashed.encode("utf-8")
    if hashed_bytes.startswith(b"$2y$"):
        hashed_bytes = b"$2b$" + hashed_bytes[4:]
    return _bcrypt_lib.checkpw(plain.encode("utf-8"), hashed_bytes)


def _bcrypt_hash(plain: str) -> str:
    """Genera hash bcrypt con salt aleatorio."""
    return _bcrypt_lib.hashpw(plain.encode("utf-8"), _bcrypt_lib.gensalt()).decode("utf-8")


class AuthService:
    """
    Servicio de autenticación.

    Equivale a la lógica de App\\Http\\Controllers\\Auth\\LoginController
    combinada con la autenticación de Laravel (Auth::guard(realm)->attempt).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def attempt(
        self,
        email: str,
        password: str,
        realm: str,
        ip: str | None = None,
    ) -> User:
        """
        Intenta autenticar al usuario.

        Returns:
            User autenticado (activo, realm correcto, password válido).

        Raises:
            ValueError: credenciales inválidas, cuenta inactiva o realm incorrecto.
        """
        user = await self._find_user(email, realm)

        if user is None or not _bcrypt_verify(password, user.password):
            raise ValueError("Credenciales inválidas o cuenta no activa.")

        if user.status != "active":
            raise ValueError("Credenciales inválidas o cuenta no activa.")

        # Actualizar último acceso
        user.last_login_at = datetime.now(timezone.utc)
        user.last_login_ip = ip
        self._db.add(user)
        await self._db.flush()

        return user

    async def _find_user(self, email: str, realm: str) -> User | None:
        result = await self._db.execute(
            select(User).where(
                User.email == email.lower(),
                User.realm == realm,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        """Verifica password contra hash bcrypt ($2y$ o $2b$)."""
        return _bcrypt_verify(plain, hashed)

    @staticmethod
    def hash_password(plain: str) -> str:
        """Genera hash bcrypt."""
        return _bcrypt_hash(plain)
