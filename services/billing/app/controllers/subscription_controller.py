"""
Billing & Subscriptions — Module F
Máquina de estados: Lead → Active → Morosa → Cancelled
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_db
from common.middleware.auth import get_current_user
from common.models.user import User

router = APIRouter(prefix="/customer/subscription", tags=["customer:billing"])


@router.get("/status")
async def subscription_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Estado actual de la suscripción del cliente. Placeholder — implementar con Stripe."""
    return {"status": "pending_implementation", "user_id": current_user.id}
