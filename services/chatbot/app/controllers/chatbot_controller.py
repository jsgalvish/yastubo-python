"""
Chatbot Integration Controller — Módulo G

Facade ligero para SofIA (AI Agent en n8n + Chatwoot).
Expone endpoints simples protegidos por API key estática para que
n8n pueda llamarlos sin necesidad de manejar JWT de admin.

Endpoints:
  GET  /chatbot/client          → busca cliente por número de documento
  POST /chatbot/reset-password  → envía email de recuperación de contraseña
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, EmailStr
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import settings
from common.database import get_db
from common.models.capitated_contract import CapitatedContract
from common.models.capitated_product_insured import CapitatedProductInsured
from common.models.company import Company

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

_api_key_header = APIKeyHeader(name="X-Chatbot-Api-Key", auto_error=False)


# ── Auth ──────────────────────────────────────────────────────────────────────


def _require_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    """Valida que el header X-Chatbot-Api-Key coincida con el configurado."""
    configured = settings.chatbot_api_key
    if not configured:
        raise HTTPException(status_code=500, detail="Chatbot API key no configurada en el servidor.")
    if api_key != configured:
        raise HTTPException(status_code=401, detail="API key inválida.")


# ── Schemas ───────────────────────────────────────────────────────────────────


class ContractInfo(BaseModel):
    contract_id: int
    contract_uuid: str
    status: str
    full_name: str | None
    document_number: str | None
    entry_date: str | None
    valid_until: str | None
    pdf_url: str


class ClientSearchResponse(BaseModel):
    found: bool
    message: str
    contracts: list[ContractInfo] = []


class ResetPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordResponse(BaseModel):
    status: str


# ── Helpers ───────────────────────────────────────────────────────────────────


def _pdf_url(uuid: str) -> str:
    """Construye la URL pública del PDF de un contrato."""
    base = settings.app_url.rstrip("/")
    return f"{base}/capitated/contracts/{uuid}/pdf"


def _translate(data) -> str | None:
    if data is None:
        return None
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            return data
    if isinstance(data, dict):
        return data.get("es") or data.get("en") or next(iter(data.values()), None)
    return str(data)


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/client", response_model=ClientSearchResponse)
async def search_client(
    doc: str = Query(description="Número de documento del cliente"),
    company_id: int = Query(description="ID de la empresa en Yastubo"),
    _auth: None = Depends(_require_api_key),
    db: AsyncSession = Depends(get_db),
) -> ClientSearchResponse:
    """
    Busca un cliente por número de documento dentro de una empresa y retorna
    sus contratos activos junto con el enlace al PDF de cada uno.
    """
    # Verificar que la empresa existe
    company_r = await db.execute(select(Company).where(Company.id == company_id))
    company = company_r.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")

    doc_clean = doc.strip()
    like = f"%{doc_clean}%"

    # Buscar contratos activos del cliente con join a persona
    stmt = (
        select(CapitatedContract, CapitatedProductInsured)
        .join(
            CapitatedProductInsured,
            CapitatedContract.person_id == CapitatedProductInsured.id,
        )
        .where(
            CapitatedContract.company_id == company_id,
            CapitatedContract.status == "active",
            or_(
                CapitatedProductInsured.document_number.ilike(like),
                CapitatedProductInsured.full_name.ilike(like),
            ),
        )
        .order_by(CapitatedContract.id.desc())
        .limit(10)
    )

    rows = (await db.execute(stmt)).all()

    if not rows:
        return ClientSearchResponse(
            found=False,
            message=f"No se encontraron contratos activos para el documento '{doc_clean}'.",
        )

    contracts = [
        ContractInfo(
            contract_id=contract.id,
            contract_uuid=str(contract.uuid),
            status=contract.status,
            full_name=person.full_name,
            document_number=person.document_number,
            entry_date=str(contract.entry_date) if contract.entry_date else None,
            valid_until=str(contract.valid_until) if contract.valid_until else None,
            pdf_url=_pdf_url(str(contract.uuid)),
        )
        for contract, person in rows
    ]

    first = contracts[0]
    message = (
        f"Se encontró a {first.full_name} (doc: {first.document_number}) "
        f"con {len(contracts)} contrato(s) activo(s)."
    )

    return ClientSearchResponse(found=True, message=message, contracts=contracts)


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def send_reset_password(
    body: ResetPasswordRequest,
    _auth: None = Depends(_require_api_key),
    db: AsyncSession = Depends(get_db),
) -> ResetPasswordResponse:
    """
    Envía un email de recuperación de contraseña al cliente.
    Siempre retorna éxito para no revelar si el email existe.
    """
    import secrets

    from common.models.user import User

    result = await db.execute(
        select(User).where(
            User.email == body.email,
            User.realm == "customer",
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if user:
        token = secrets.token_urlsafe(48)
        user.remember_token = token
        await db.commit()

        try:
            from common.notifications.customer.reset_password import send_reset_password_customer

            url = f"{settings.app_url}/customer/reset-password/{token}?email={user.email}"
            await send_reset_password_customer(user, url, minutes=30)
        except Exception:
            logger.warning("No se pudo enviar email de reset a %s", body.email)

    return ResetPasswordResponse(
        status="Si el correo está registrado, recibirás un enlace de recuperación en breve."
    )
