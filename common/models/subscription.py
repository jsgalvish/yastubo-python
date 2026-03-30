"""Modelo de suscripciones retail (B2C) — Módulo F."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.models.base import Base, TimestampMixin


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    plan_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="usd", nullable=False)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    referral_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    referred_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Status constants
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_PAST_DUE = "past_due"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"


class ReferralCommission(TimestampMixin, Base):
    __tablename__ = "referral_commissions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    referrer_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    referred_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    subscription_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    commission_amount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="usd", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
