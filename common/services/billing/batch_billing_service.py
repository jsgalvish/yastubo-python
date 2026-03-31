"""
Servicio de facturación automática para lotes capitados.
Genera Stripe Invoice al procesar un batch con beneficiarios activos.
"""
from __future__ import annotations

import os
from typing import Optional

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.capitated_batch_log import CapitatedBatchLog
from common.models.company import Company
from common.models.plan_version import PlanVersion
from common.models.product import Product

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")


class BatchBillingService:
    """Genera facturas en Stripe al procesar lotes capitados."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_invoice_for_batch(
        self, batch: CapitatedBatchLog, company: Company
    ) -> Optional[dict]:
        """
        Genera un Stripe Invoice para un batch procesado.

        Calcula: total_applied × precio promedio del plan → crea invoice items → finaliza invoice.
        Returns dict con invoice_id y amount, o None si no se puede facturar.
        """
        if not company.stripe_customer_id:
            return None

        if batch.total_applied <= 0:
            return None

        if not stripe.api_key:
            return None

        # Get the average price from active plan versions of this company's products
        products_r = await self.db.execute(
            select(Product.id).where(Product.company_id == company.id, Product.status == "active")
        )
        product_ids = [r[0] for r in products_r.all()]

        if not product_ids:
            return None

        pvs = await self.db.execute(
            select(PlanVersion.public_price)
            .where(
                PlanVersion.product_id.in_(product_ids),
                PlanVersion.status == "active",
                PlanVersion.public_price.isnot(None),
            )
        )
        prices = [float(p[0]) for p in pvs.all()]
        avg_price = sum(prices) / len(prices) if prices else 0

        if avg_price <= 0:
            return None

        total_amount_cents = int(batch.total_applied * avg_price * 100)

        try:
            # Create invoice
            invoice = stripe.Invoice.create(
                customer=company.stripe_customer_id,
                collection_method="send_invoice",
                days_until_due=30,
                metadata={
                    "batch_id": str(batch.id),
                    "company_id": str(company.id),
                    "coverage_month": str(batch.coverage_month),
                    "total_applied": str(batch.total_applied),
                },
            )

            # Create invoice item
            stripe.InvoiceItem.create(
                customer=company.stripe_customer_id,
                invoice=invoice.id,
                amount=total_amount_cents,
                currency="usd",
                description=f"Cobertura capitada {batch.coverage_month} — {batch.total_applied} beneficiarios × ${avg_price:.2f}",
            )

            # Finalize (sends the invoice)
            stripe.Invoice.finalize_invoice(invoice.id)

            return {
                "invoice_id": invoice.id,
                "amount_cents": total_amount_cents,
                "total_applied": batch.total_applied,
                "avg_price": avg_price,
            }

        except stripe.StripeError as e:
            # Log error but don't block batch processing
            print(f"[BatchBilling] Stripe error: {e}")
            return None
