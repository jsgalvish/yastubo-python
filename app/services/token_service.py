from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"


def create_access_token(
    user_id: int,
    realm: str,
    force_password_change: bool = False,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Genera un JWT de acceso.

    Payload:
      sub  — user_id (str)
      realm — "admin" | "customer"
      force_password_change — bool
      exp  — timestamp de expiración
      + cualquier campo adicional pasado en extra_claims
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.session_lifetime_minutes
    )
    payload: dict = {
        "sub": str(user_id),
        "realm": realm,
        "force_password_change": force_password_change,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decodifica y valida un JWT.
    Lanza JWTError si el token es inválido o expiró.
    """
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
