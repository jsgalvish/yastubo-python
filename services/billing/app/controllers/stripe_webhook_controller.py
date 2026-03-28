"""
Stripe Webhook Controller — Module F
Recibe eventos de Stripe y actualiza el estado de la suscripción.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException

router = APIRouter(prefix="/webhooks/stripe", tags=["webhooks:stripe"])


@router.post("")
async def stripe_webhook(request: Request) -> dict:
    """
    Recibe webhooks de Stripe.
    Eventos a manejar:
    - invoice.paid           → Active
    - invoice.payment_failed → Morosa
    - customer.subscription.deleted → Cancelled
    Placeholder — implementar con stripe SDK + idempotency keys.
    """
    payload = await request.body()
    # TODO: verify stripe signature, process event, update subscription state
    return {"received": True}
