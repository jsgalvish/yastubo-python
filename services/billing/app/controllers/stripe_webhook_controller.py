"""
Stripe Webhook Controller — Module F
Procesa eventos de Stripe y actualiza estado de suscripciones.
"""

from __future__ import annotations

import os
from datetime import datetime

import stripe
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import AsyncSessionLocal
from common.models.subscription import Subscription
from common.services.zoho_crm_service import ZohoCrmService
from common.support.audit import Audit

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

router = APIRouter(prefix="/webhooks/stripe", tags=["webhooks:stripe"])


@router.post("")
async def stripe_webhook(request: Request) -> dict:
    """
    Procesa webhooks de Stripe.
    Eventos manejados:
    - invoice.paid              → subscription status = active
    - invoice.payment_failed    → subscription status = past_due
    - customer.subscription.deleted → subscription status = cancelled
    - customer.subscription.updated → sync period dates
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # Verify signature if webhook secret is configured
    if WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
        except (ValueError, stripe.SignatureVerificationError):
            raise HTTPException(status_code=400, detail="Firma de webhook inválida.")
    else:
        import json

        event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)

    event_type = event.type
    data = event.data.object

    async with AsyncSessionLocal() as db:
        if event_type == "invoice.paid":
            await _handle_invoice_paid(db, data)
        elif event_type == "invoice.payment_failed":
            await _handle_payment_failed(db, data)
        elif event_type == "customer.subscription.deleted":
            await _handle_subscription_deleted(db, data)
        elif event_type == "customer.subscription.updated":
            await _handle_subscription_updated(db, data)

    return {"received": True, "type": event_type}


async def _find_subscription(db: AsyncSession, stripe_sub_id: str) -> Subscription | None:
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    return result.scalar_one_or_none()


async def _handle_invoice_paid(db: AsyncSession, invoice: dict) -> None:
    """Pago exitoso — activar suscripción."""
    stripe_sub_id = invoice.get("subscription")
    if not stripe_sub_id:
        return

    sub = await _find_subscription(db, stripe_sub_id)
    if not sub:
        return

    sub.status = Subscription.STATUS_ACTIVE
    period_end = invoice.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end")
    if period_end:
        sub.current_period_end = datetime.utcfromtimestamp(period_end)

    await db.commit()
    await Audit.log(
        db,
        action="subscription.payment_succeeded",
        context={
            "subscription_id": sub.id,
            "user_id": sub.user_id,
        },
    )

    # Zoho: update deal stage → Closed Won
    try:
        crm = ZohoCrmService(db)
        await crm.update_deal_stage(sub.id, "active")
    except Exception:
        pass


async def _handle_payment_failed(db: AsyncSession, invoice: dict) -> None:
    """Pago fallido — marcar como morosa."""
    stripe_sub_id = invoice.get("subscription")
    if not stripe_sub_id:
        return

    sub = await _find_subscription(db, stripe_sub_id)
    if not sub:
        return

    sub.status = Subscription.STATUS_PAST_DUE
    await db.commit()
    await Audit.log(
        db,
        action="subscription.payment_failed",
        context={
            "subscription_id": sub.id,
            "user_id": sub.user_id,
        },
    )

    # Zoho: update deal stage → Negotiation/Review
    try:
        crm = ZohoCrmService(db)
        await crm.update_deal_stage(sub.id, "past_due")
    except Exception:
        pass


async def _handle_subscription_deleted(db: AsyncSession, stripe_sub: dict) -> None:
    """Suscripción cancelada en Stripe."""
    sub = await _find_subscription(db, stripe_sub.get("id", ""))
    if not sub:
        return

    sub.status = Subscription.STATUS_CANCELLED
    sub.canceled_at = datetime.utcnow()
    await db.commit()
    await Audit.log(
        db,
        action="subscription.cancelled",
        context={
            "subscription_id": sub.id,
            "user_id": sub.user_id,
        },
    )

    # Zoho: update deal stage → Closed Lost
    try:
        crm = ZohoCrmService(db)
        await crm.update_deal_stage(sub.id, "cancelled")
    except Exception:
        pass


async def _handle_subscription_updated(db: AsyncSession, stripe_sub: dict) -> None:
    """Actualización de suscripción — sincronizar fechas."""
    sub = await _find_subscription(db, stripe_sub.get("id", ""))
    if not sub:
        return

    new_status = stripe_sub.get("status")
    if new_status:
        status_map = {
            "active": Subscription.STATUS_ACTIVE,
            "past_due": Subscription.STATUS_PAST_DUE,
            "canceled": Subscription.STATUS_CANCELLED,
            "unpaid": Subscription.STATUS_PAST_DUE,
        }
        sub.status = status_map.get(new_status, sub.status)

    period_end = stripe_sub.get("current_period_end")
    if period_end:
        sub.current_period_end = datetime.utcfromtimestamp(period_end)

    period_start = stripe_sub.get("current_period_start")
    if period_start:
        sub.current_period_start = datetime.utcfromtimestamp(period_start)

    await db.commit()
