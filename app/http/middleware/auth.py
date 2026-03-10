from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.token_service import decode_token
from app.support.realm import Realm

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado.",
    headers={"WWW-Authenticate": "Bearer"},
)
_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Sin permisos para este dominio.",
)


async def _extract_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if not credentials:
        raise _UNAUTHORIZED
    return credentials.credentials


async def get_current_user(
    token: str = Depends(_extract_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency: valida el JWT y retorna el usuario autenticado.
    Equivale al guard de Laravel.
    """
    try:
        payload = decode_token(token)
    except JWTError:
        raise _UNAUTHORIZED

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise _UNAUTHORIZED

    result = await db.execute(
        select(User).where(
            User.id == int(user_id),
            User.deleted_at.is_(None),
            User.status == "active",
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise _UNAUTHORIZED

    return user


async def get_admin_user(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    """
    Dependency: usuario autenticado del dominio admin.
    Equivale al middleware 'admin' de PHP.
    """
    Realm.set_current("admin")
    if not user.is_admin():
        raise _FORBIDDEN
    return user


async def get_customer_user(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    """
    Dependency: usuario autenticado del dominio customer.
    Equivale al middleware 'customer' de PHP.
    """
    Realm.set_current("customer")
    if not user.is_customer():
        raise _FORBIDDEN
    return user
