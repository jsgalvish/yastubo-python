"""
Stripe Connect Controller — Module F
Gestión de cuentas Express para vendedores/referidores.

Endpoints:
  POST   /admin/connect/accounts          → crear cuenta Express
  GET    /admin/connect/accounts           → listar cuentas
  POST   /admin/connect/accounts/{id}/link → generar link de onboarding
  POST   /admin/connect/transfer           → transferir comisión
"""

from __future__ import annotations

import os

import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common.middleware.permission import require_permission
from common.models.user import User

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

router = APIRouter(prefix="/admin/connect", tags=["admin:connect"])


class CreateAccountRequest(BaseModel):
    email: str
    name: str
    user_id: int | None = None
    country: str = "US"


class CreateAccountResponse(BaseModel):
    account_id: str
    email: str
    onboarding_url: str | None = None


class TransferRequest(BaseModel):
    destination_account_id: str
    amount_cents: int
    currency: str = "usd"
    description: str = ""


@router.post("/accounts", response_model=CreateAccountResponse)
async def create_express_account(
    body: CreateAccountRequest,
    _current_user: User = Depends(require_permission("admin.config.read")),
) -> CreateAccountResponse:
    """Crea una cuenta Express de Stripe Connect para un vendedor."""
    try:
        account = stripe.Account.create(
            type="express",
            country=body.country,
            email=body.email,
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            business_type="individual",
            metadata={
                "user_id": str(body.user_id) if body.user_id else "",
                "name": body.name,
            },
        )

        # Generate onboarding link
        base_url = os.getenv("APP_URL", "http://localhost:5173")
        link = stripe.AccountLink.create(
            account=account.id,
            refresh_url=f"{base_url}/admin/subscriptions",
            return_url=f"{base_url}/admin/subscriptions?connect_onboarded=true",
            type="account_onboarding",
        )

        return CreateAccountResponse(
            account_id=account.id,
            email=body.email,
            onboarding_url=link.url,
        )

    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Error Stripe Connect: {e!s}")


@router.get("/accounts")
async def list_express_accounts(
    _current_user: User = Depends(require_permission("admin.config.read")),
) -> dict:
    """Lista cuentas Express conectadas."""
    try:
        accounts = stripe.Account.list(limit=100)
        data = []
        for acc in accounts.data:
            meta = getattr(acc, "metadata", {}) or {}
            data.append(
                {
                    "id": acc.id,
                    "email": getattr(acc, "email", None),
                    "country": getattr(acc, "country", None),
                    "charges_enabled": getattr(acc, "charges_enabled", False),
                    "payouts_enabled": getattr(acc, "payouts_enabled", False),
                    "name": meta.get("name", "") if isinstance(meta, dict) else "",
                    "user_id": meta.get("user_id", "") if isinstance(meta, dict) else "",
                }
            )
        return {"data": data}
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Error: {e!s}")


@router.post("/accounts/{account_id}/link")
async def create_onboarding_link(
    account_id: str,
    _current_user: User = Depends(require_permission("admin.config.read")),
) -> dict:
    """Genera un link de onboarding para una cuenta Express."""
    base_url = os.getenv("APP_URL", "http://localhost:5173")
    try:
        link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=f"{base_url}/admin/subscriptions",
            return_url=f"{base_url}/admin/subscriptions?connect_onboarded=true",
            type="account_onboarding",
        )
        return {"url": link.url}
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Error: {e!s}")


@router.post("/transfer")
async def create_transfer(
    body: TransferRequest,
    _current_user: User = Depends(require_permission("admin.config.read")),
) -> dict:
    """Transfiere fondos a una cuenta Express (pago de comisión)."""
    try:
        transfer = stripe.Transfer.create(
            amount=body.amount_cents,
            currency=body.currency,
            destination=body.destination_account_id,
            description=body.description or "Comisión Yastubo",
        )
        return {"transfer_id": transfer.id, "amount": body.amount_cents, "status": "completed"}
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Error: {e!s}")
