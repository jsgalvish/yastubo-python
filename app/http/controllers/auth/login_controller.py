from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.http.middleware.auth import get_admin_user, get_customer_user
from app.http.requests.auth.login_request import LoginRequest, TokenResponse
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.token_service import create_access_token

router = APIRouter(tags=["auth"])


async def _do_login(
    realm: str,
    body: LoginRequest,
    request: Request,
    db: AsyncSession,
) -> TokenResponse:
    """Lógica compartida de login para admin y customer."""
    service = AuthService(db)
    try:
        user: User = await service.attempt(
            email=body.email,
            password=body.password,
            realm=realm,
            ip=request.client.host if request.client else None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    await db.commit()

    token = create_access_token(
        user_id=user.id,
        realm=realm,
        force_password_change=bool(user.force_password_change),
    )
    return TokenResponse(
        access_token=token,
        force_password_change=bool(user.force_password_change),
    )


@router.post("/admin/login", response_model=TokenResponse)
async def admin_login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Login de dominio admin.
    Equivale a Auth::guard('admin')->attempt(...) de PHP.
    """
    return await _do_login("admin", body, request, db)


@router.post("/customer/login", response_model=TokenResponse)
async def customer_login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Login de dominio customer.
    Equivale a Auth::guard('customer')->attempt(...) de PHP.
    """
    return await _do_login("customer", body, request, db)


@router.post("/admin/logout", status_code=status.HTTP_204_NO_CONTENT)
async def admin_logout(
    _user: User = Depends(get_admin_user),
) -> None:
    """
    Logout de admin (JWT stateless — el cliente descarta el token).
    Equivale a auth('admin')->logout() de PHP.
    """


@router.post("/customer/logout", status_code=status.HTTP_204_NO_CONTENT)
async def customer_logout(
    _user: User = Depends(get_customer_user),
) -> None:
    """
    Logout de customer (JWT stateless — el cliente descarta el token).
    """
