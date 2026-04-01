"""
Zoho CRM Sync Service — lógica de negocio para sincronización.

Mapea entidades locales a módulos Zoho CRM:
  Company     → Accounts
  User+Sub    → Contacts + Deals
  Checkout    → Leads

Si Zoho no está configurado (sin OAuth creds), opera en modo DRY-RUN:
logea todo a zoho_sync_log con zoho_record_id='DRY-RUN'.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.integrations.zoho_client import zoho_client
from common.models.zoho_sync_log import ZohoSyncLog

logger = logging.getLogger("zoho_crm_service")

# ── Deal stages mapping ──────────────────────────────────────────────

STAGE_ACTIVE = "Closed Won"
STAGE_CANCELLED = "Closed Lost"
STAGE_PAST_DUE = "Negotiation/Review"
STAGE_PENDING = "Qualification"


class ZohoCrmService:
    """Servicio de sincronización Yastubo → Zoho CRM."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Helpers ───────────────────────────────────────────────────────

    async def _find_existing_sync(
        self, entity_type: str, local_id: int
    ) -> ZohoSyncLog | None:
        result = await self.db.execute(
            select(ZohoSyncLog).where(
                ZohoSyncLog.entity_type == entity_type,
                ZohoSyncLog.local_id == local_id,
            )
        )
        return result.scalar_one_or_none()

    async def _log_sync(
        self,
        entity_type: str,
        local_id: int,
        zoho_module: str,
        zoho_record_id: str,
        sync_data: dict[str, Any],
    ) -> ZohoSyncLog:
        existing = await self._find_existing_sync(entity_type, local_id)
        if existing:
            existing.zoho_record_id = zoho_record_id
            existing.sync_data = json.dumps(sync_data, default=str)
            existing.synced_at = datetime.utcnow()
            await self.db.flush()
            return existing

        log = ZohoSyncLog(
            entity_type=entity_type,
            local_id=local_id,
            zoho_module=zoho_module,
            zoho_record_id=zoho_record_id,
            sync_data=json.dumps(sync_data, default=str),
            synced_at=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.flush()
        return log

    # ── Company → Account ─────────────────────────────────────────────

    async def sync_company_to_account(self, company: Any) -> dict[str, Any]:
        """Sincroniza una empresa local como Zoho Account."""
        data = {
            "Account_Name": company.name,
            "Phone": company.phone or "",
            "Description": company.description or "",
        }
        if hasattr(company, "email") and company.email:
            data["Website"] = ""  # Zoho Accounts no tiene Email directo

        zoho_id = "DRY-RUN"
        action = "dry-run"

        if zoho_client.is_configured:
            existing = await self._find_existing_sync("company", company.id)
            if existing and existing.zoho_record_id != "DRY-RUN":
                result = await zoho_client.update_record(
                    "Accounts", existing.zoho_record_id, data
                )
                zoho_id = existing.zoho_record_id
                action = "updated"
            else:
                result = await zoho_client.create_record("Accounts", data)
                zoho_id = result.get("id", "ERROR")
                action = "created"
            logger.info("Company %s → Account %s (%s)", company.id, zoho_id, action)
        else:
            logger.info("DRY-RUN: Company %s → Account (no creds)", company.id)

        sync_data = {**data, "status": company.status, "action": action}
        await self._log_sync("company", company.id, "Accounts", zoho_id, sync_data)
        await self.db.commit()
        return {"zoho_id": zoho_id, "action": action}

    # ── Subscription → Contact + Deal ─────────────────────────────────

    async def sync_subscription_to_contact_deal(
        self, subscription: Any, user: Any
    ) -> dict[str, Any]:
        """Sincroniza suscripción activa: crea/actualiza Contact y Deal."""
        first = getattr(user, "first_name", "") or ""
        last = getattr(user, "last_name", "") or ""
        email = getattr(user, "email", "") or ""
        full_name = f"{first} {last}".strip() or email

        # ── Contact ──
        contact_data = {
            "First_Name": first or full_name,
            "Last_Name": last or full_name,
            "Email": email,
        }
        contact_zoho_id = "DRY-RUN"

        if zoho_client.is_configured:
            existing_contact = await self._find_existing_sync(
                "subscription_contact", subscription.id
            )
            if existing_contact and existing_contact.zoho_record_id != "DRY-RUN":
                contact_zoho_id = existing_contact.zoho_record_id
                await zoho_client.update_record("Contacts", contact_zoho_id, contact_data)
            else:
                # Buscar por email primero para evitar duplicados
                found = await zoho_client.search_records(
                    "Contacts", f"(Email:equals:{email})"
                )
                if found:
                    contact_zoho_id = found[0]["id"]
                    await zoho_client.update_record("Contacts", contact_zoho_id, contact_data)
                else:
                    result = await zoho_client.create_record("Contacts", contact_data)
                    contact_zoho_id = result.get("id", "ERROR")
            logger.info("Subscription %s → Contact %s", subscription.id, contact_zoho_id)
        else:
            logger.info("DRY-RUN: Subscription %s → Contact", subscription.id)

        await self._log_sync(
            "subscription_contact",
            subscription.id,
            "Contacts",
            contact_zoho_id,
            {**contact_data, "action": "upsert"},
        )

        # ── Deal ──
        amount = (getattr(subscription, "amount_cents", 0) or 0) / 100
        status = getattr(subscription, "status", "pending")
        stage = {
            "active": STAGE_ACTIVE,
            "cancelled": STAGE_CANCELLED,
            "past_due": STAGE_PAST_DUE,
        }.get(status, STAGE_PENDING)

        deal_data = {
            "Deal_Name": f"Suscripción Yastubo - {full_name}",
            "Amount": amount,
            "Stage": stage,
            "Closing_Date": datetime.utcnow().strftime("%Y-%m-%d"),
        }
        # Link contact to deal
        if contact_zoho_id and contact_zoho_id != "DRY-RUN":
            deal_data["Contact_Name"] = {"id": contact_zoho_id}

        deal_zoho_id = "DRY-RUN"

        if zoho_client.is_configured:
            existing_deal = await self._find_existing_sync("deal", subscription.id)
            if existing_deal and existing_deal.zoho_record_id != "DRY-RUN":
                deal_zoho_id = existing_deal.zoho_record_id
                await zoho_client.update_record("Deals", deal_zoho_id, deal_data)
            else:
                result = await zoho_client.create_record("Deals", deal_data)
                deal_zoho_id = result.get("id", "ERROR")
            logger.info("Subscription %s → Deal %s (stage=%s)", subscription.id, deal_zoho_id, stage)
        else:
            logger.info("DRY-RUN: Subscription %s → Deal (stage=%s)", subscription.id, stage)

        await self._log_sync(
            "deal",
            subscription.id,
            "Deals",
            deal_zoho_id,
            {**deal_data, "contact_zoho_id": contact_zoho_id, "action": "upsert"},
        )
        await self.db.commit()
        return {"contact_id": contact_zoho_id, "deal_id": deal_zoho_id}

    # ── Update Deal stage ─────────────────────────────────────────────

    async def update_deal_stage(
        self, subscription_id: int, new_status: str
    ) -> dict[str, Any]:
        """Actualiza el Stage del Deal cuando cambia el estado de la suscripción."""
        stage = {
            "active": STAGE_ACTIVE,
            "cancelled": STAGE_CANCELLED,
            "past_due": STAGE_PAST_DUE,
            "pending": STAGE_PENDING,
        }.get(new_status, STAGE_PENDING)

        existing = await self._find_existing_sync("deal", subscription_id)
        if not existing:
            logger.warning("No deal sync found for subscription %s", subscription_id)
            return {"status": "no_deal_found"}

        zoho_id = existing.zoho_record_id

        if zoho_client.is_configured and zoho_id != "DRY-RUN":
            await zoho_client.update_record("Deals", zoho_id, {"Stage": stage})
            logger.info("Deal %s stage → %s", zoho_id, stage)
        else:
            logger.info("DRY-RUN: Deal %s stage → %s", zoho_id, stage)

        # Update sync log
        sync_data = json.loads(existing.sync_data) if existing.sync_data else {}
        sync_data["Stage"] = stage
        sync_data["action"] = "stage_update"
        existing.sync_data = json.dumps(sync_data, default=str)
        existing.synced_at = datetime.utcnow()
        await self.db.commit()
        return {"zoho_id": zoho_id, "stage": stage}

    # ── Lead from abandoned checkout ──────────────────────────────────

    async def create_lead_from_checkout(
        self,
        email: str,
        first_name: str = "",
        last_name: str = "",
        utm_source: str = "",
        utm_medium: str = "",
        utm_campaign: str = "",
    ) -> dict[str, Any]:
        """Crea un Lead en Zoho cuando un checkout es abandonado."""
        lead_data = {
            "First_Name": first_name or email.split("@")[0],
            "Last_Name": last_name or email.split("@")[0],
            "Email": email,
            "Company": "Individual",
            "Lead_Status": "Checkout Abandoned",
            "Lead_Source": "Online Store",
            "Description": f"UTM: source={utm_source}, medium={utm_medium}, campaign={utm_campaign}",
        }

        zoho_id = "DRY-RUN"

        if zoho_client.is_configured:
            # Upsert por email para evitar duplicados
            result = await zoho_client.upsert_record(
                "Leads", lead_data, ["Email"]
            )
            zoho_id = result.get("id", "ERROR")
            logger.info("Lead %s → %s", email, zoho_id)
        else:
            logger.info("DRY-RUN: Lead %s", email)

        await self._log_sync(
            "lead", 0, "Leads", zoho_id, {**lead_data, "action": "upsert"}
        )
        await self.db.commit()
        return {"zoho_id": zoho_id}
