"""
Billing & Subscriptions — Module F
Endpoints para suscripciones retail (B2C) con Stripe.

Endpoints:
  GET    /customer/subscription/status     → estado actual
  POST   /customer/subscription/create     → crear suscripción
  POST   /customer/subscription/cancel     → cancelar suscripción
  GET    /customer/subscription/portal     → link al portal de Stripe
  GET    /admin/subscriptions              → listado admin
  GET    /admin/subscriptions/stats        → métricas
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_db
from common.middleware.auth import get_current_user
from common.middleware.permission import require_permission
from common.models.subscription import ReferralCommission, Subscription
from common.models.user import User

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "price_1TGevjIpOl9JJO5pfRkAK1dJ")
COMMISSION_PERCENT = 10  # 10% referral commission

router = APIRouter(tags=["customer:billing"])


# ── Schemas ────────────────────────────────────────────────────────────────


class SubscriptionStatusOut(BaseModel):
    id: int | None = None
    status: str
    plan_name: str | None = None
    amount: float | None = None
    currency: str = "usd"
    current_period_end: str | None = None
    referral_code: str | None = None
    stripe_subscription_id: str | None = None


class CreateSubscriptionRequest(BaseModel):
    referral_code: str | None = None


class SubscriptionAdminOut(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    user_email: str | None = None
    status: str
    plan_name: str | None = None
    amount: float
    currency: str
    current_period_end: str | None = None
    referral_code: str | None = None
    created_at: str | None = None


class StatsOut(BaseModel):
    total_subscriptions: int
    active: int
    past_due: int
    cancelled: int
    mrr_cents: int


# ── Customer endpoints ─────────────────────────────────────────────────────


@router.get("/customer/subscription/status", response_model=SubscriptionStatusOut)
async def subscription_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionStatusOut:
    """Estado actual de la suscripción del cliente."""
    sub = (await db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )).scalar_one_or_none()

    if not sub:
        return SubscriptionStatusOut(status="none")

    return SubscriptionStatusOut(
        id=sub.id,
        status=sub.status,
        plan_name=sub.plan_name,
        amount=sub.amount_cents / 100 if sub.amount_cents else None,
        currency=sub.currency,
        current_period_end=str(sub.current_period_end) if sub.current_period_end else None,
        referral_code=sub.referral_code,
        stripe_subscription_id=sub.stripe_subscription_id,
    )


@router.post("/customer/subscription/create", response_model=SubscriptionStatusOut)
async def create_subscription(
    body: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionStatusOut:
    """Crea una suscripción en Stripe y registra localmente."""
    # Check existing active subscription
    existing = (await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_(["active", "past_due"]),
        )
    )).scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=422, detail="Ya tienes una suscripción activa.")

    # Create Stripe customer
    try:
        stripe_customer = stripe.Customer.create(
            email=current_user.email,
            name=f"{current_user.first_name} {current_user.last_name or ''}".strip(),
            metadata={"user_id": str(current_user.id)},
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Error con Stripe: {str(e)}")

    # Create Stripe subscription
    try:
        stripe_sub = stripe.Subscription.create(
            customer=stripe_customer.id,
            items=[{"price": STRIPE_PRICE_ID}],
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"],
            metadata={"user_id": str(current_user.id)},
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Error creando suscripción: {str(e)}")

    # Check referral
    referred_by = None
    if body.referral_code:
        referrer_sub = (await db.execute(
            select(Subscription).where(Subscription.referral_code == body.referral_code)
        )).scalar_one_or_none()
        if referrer_sub:
            referred_by = referrer_sub.user_id

    # Save locally
    sub = Subscription()
    sub.user_id = current_user.id
    sub.stripe_customer_id = stripe_customer.id
    sub.stripe_subscription_id = stripe_sub.id
    sub.stripe_price_id = STRIPE_PRICE_ID
    sub.status = stripe_sub.status or "pending"
    sub.plan_name = "Yastubo - Repatriación Funeraria"
    sub.amount_cents = 1499
    sub.currency = "usd"
    sub.referral_code = f"REF-{uuid.uuid4().hex[:8].upper()}"
    sub.referred_by_user_id = referred_by

    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    # Create referral commission if applicable
    if referred_by:
        commission = ReferralCommission()
        commission.referrer_user_id = referred_by
        commission.referred_user_id = current_user.id
        commission.subscription_id = sub.id
        commission.commission_amount_cents = int(sub.amount_cents * COMMISSION_PERCENT / 100)
        commission.currency = "usd"
        commission.status = "pending"
        db.add(commission)
        await db.commit()

    return SubscriptionStatusOut(
        id=sub.id,
        status=sub.status,
        plan_name=sub.plan_name,
        amount=sub.amount_cents / 100,
        currency=sub.currency,
        referral_code=sub.referral_code,
        stripe_subscription_id=sub.stripe_subscription_id,
    )


@router.post("/customer/subscription/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancela la suscripción del cliente."""
    sub = (await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_(["active", "past_due"]),
        )
    )).scalar_one_or_none()

    if not sub:
        raise HTTPException(status_code=404, detail="No tienes suscripción activa.")

    # Cancel in Stripe
    if sub.stripe_subscription_id:
        try:
            stripe.Subscription.cancel(sub.stripe_subscription_id)
        except stripe.StripeError:
            pass  # Still cancel locally

    sub.status = Subscription.STATUS_CANCELLED
    sub.canceled_at = datetime.utcnow()
    await db.commit()

    return {"message": "Suscripción cancelada.", "status": "cancelled"}


# ── Admin endpoints ────────────────────────────────────────────────────────


@router.get("/admin/subscriptions")
async def admin_list_subscriptions(
    status: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=15, ge=1, le=100),
    _current_user: User = Depends(require_permission("admin.config.read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Listado de suscripciones para admin."""
    base_q = select(Subscription)
    if status != "all":
        base_q = base_q.where(Subscription.status == status)

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    items = list((await db.execute(
        base_q.order_by(Subscription.id.desc()).offset((page - 1) * per_page).limit(per_page)
    )).scalars().all())

    # Enrich with user names
    user_ids = list({s.user_id for s in items})
    user_map: dict = {}
    if user_ids:
        users_r = await db.execute(select(User).where(User.id.in_(user_ids)))
        user_map = {u.id: u for u in users_r.scalars().all()}

    data = []
    for s in items:
        u = user_map.get(s.user_id)
        data.append(SubscriptionAdminOut(
            id=s.id,
            user_id=s.user_id,
            user_name=f"{u.first_name} {u.last_name or ''}" if u else None,
            user_email=u.email if u else None,
            status=s.status,
            plan_name=s.plan_name,
            amount=s.amount_cents / 100,
            currency=s.currency,
            current_period_end=str(s.current_period_end) if s.current_period_end else None,
            referral_code=s.referral_code,
            created_at=str(s.created_at) if s.created_at else None,
        ))

    return {"data": data, "meta": {"total": total, "page": page, "per_page": per_page}}


@router.get("/admin/subscriptions/stats", response_model=StatsOut)
async def admin_subscription_stats(
    _current_user: User = Depends(require_permission("admin.config.read")),
    db: AsyncSession = Depends(get_db),
) -> StatsOut:
    """Métricas globales de suscripciones."""
    total = (await db.execute(select(func.count()).select_from(Subscription))).scalar() or 0
    active = (await db.execute(
        select(func.count()).select_from(
            select(Subscription).where(Subscription.status == "active").subquery()
        )
    )).scalar() or 0
    past_due = (await db.execute(
        select(func.count()).select_from(
            select(Subscription).where(Subscription.status == "past_due").subquery()
        )
    )).scalar() or 0
    cancelled = (await db.execute(
        select(func.count()).select_from(
            select(Subscription).where(Subscription.status == "cancelled").subquery()
        )
    )).scalar() or 0
    mrr = (await db.execute(
        select(func.sum(Subscription.amount_cents)).where(Subscription.status == "active")
    )).scalar() or 0

    return StatsOut(
        total_subscriptions=total,
        active=active,
        past_due=past_due,
        cancelled=cancelled,
        mrr_cents=mrr,
    )
