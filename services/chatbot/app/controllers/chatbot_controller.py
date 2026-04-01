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
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import settings
from common.database import get_db
from common.models.capitated_contract import CapitatedContract
from common.models.capitated_product_insured import CapitatedProductInsured
from common.models.company import Company

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

# ── Chat with AI ─────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    reply: str
    contracts: list[dict] = []


async def _search_contracts(doc: str, db: AsyncSession) -> list[dict]:
    """Busca contratos capitados Y suscripciones retail por documento o nombre."""
    from common.models.subscription import Subscription
    from common.models.user import User

    doc_clean = doc.strip()
    like = f"%{doc_clean}%"
    results: list[dict] = []

    # 1. Buscar contratos capitados
    stmt = (
        select(CapitatedContract, CapitatedProductInsured)
        .join(
            CapitatedProductInsured,
            CapitatedContract.person_id == CapitatedProductInsured.id,
        )
        .where(
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

    for contract, person in rows:
        results.append({
            "full_name": person.full_name,
            "document_number": person.document_number,
            "status": contract.status,
            "type": "Contrato Capitado",
            "pdf_url": _pdf_url(str(contract.uuid)),
        })

    # 2. Buscar suscripciones retail por nombre o email
    sub_stmt = (
        select(Subscription, User)
        .join(User, Subscription.user_id == User.id)
        .where(
            Subscription.status == "active",
            or_(
                User.email.ilike(like),
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.display_name.ilike(like),
            ),
        )
        .order_by(Subscription.id.desc())
        .limit(10)
    )
    sub_rows = (await db.execute(sub_stmt)).all()

    for sub, user in sub_rows:
        name = user.display_name or f"{user.first_name} {user.last_name or ''}".strip()
        results.append({
            "full_name": name,
            "document_number": user.email,
            "status": sub.status,
            "type": "Suscripción Yastubo",
            "plan": sub.plan_name,
            "referral_code": sub.referral_code,
            "pdf_url": "",
        })

    return results


import re as _re
import random as _random


def _detect_intent(text: str) -> tuple[str, str | None]:
    """Detecta la intención del usuario y extrae datos relevantes."""
    t = text.lower().strip()

    # Link de pago / referido / compartir (ANTES de voucher para no confundir)
    if any(w in t for w in ["link de pago", "enlace de pago", "botón de pago", "boton de pago", "compartir", "referir", "invitar", "generar link", "genera un link", "generame un link", "generame un boton"]):
        name_m = _re.search(r"[Bb]uscar por nombre:\s*(.+)", text)
        if name_m:
            return "referral_link", name_m.group(1).strip()
        return "referral_link", None

    # Buscar por nombre explícito (desde widget con usuario logueado)
    name_match = _re.search(r"[Bb]uscar por nombre:\s*(.+)", text)

    # Voucher / certificado / contrato / descargar
    if any(w in t for w in ["voucher", "certificado", "contrato", "descargar", "pdf", "comprobante", "constancia", "bajar"]):
        # Buscar un número de documento en el texto
        nums = _re.findall(r"\d{5,15}", t)
        if nums:
            return "search_doc", nums[0]
        # Si tiene nombre del widget, buscar por nombre
        if name_match:
            return "search_name", name_match.group(1).strip()
        # Buscar nombre (más de 2 palabras con mayúsculas)
        words = text.strip().split()
        name_words = [w for w in words if w[0:1].isupper() and len(w) > 2]
        if len(name_words) >= 2:
            return "search_name", " ".join(name_words)
        return "ask_doc", None

    # Si solo mandan un número (posible documento después de que SofIA preguntó)
    nums = _re.findall(r"^\d{5,15}$", t)
    if nums:
        return "search_doc", nums[0]

    # Si tiene nombre del widget pero no pidió nada específico, buscar por nombre
    if name_match:
        return "search_name", name_match.group(1).strip()

    # Saludo
    if any(w in t for w in ["hola", "buenos", "buenas", "hey", "hi", "hello"]):
        return "greeting", None

    # Precio / costo
    if any(w in t for w in ["precio", "costo", "cuanto", "cuánto", "vale", "cobran", "tarifa"]):
        return "pricing", None

    # Qué es / info
    if any(w in t for w in ["qué es", "que es", "información", "informacion", "cómo funciona", "como funciona", "explica", "servicios"]):
        return "info", None

    # Cobertura
    if any(w in t for w in ["cobertura", "cubre", "incluye", "beneficio"]):
        return "coverage", None

    # Edad
    if any(w in t for w in ["edad", "años", "viejo", "mayor", "limite"]):
        return "age", None

    # País
    if any(w in t for w in ["país", "pais", "países", "paises", "colombia", "mexico", "peru", "latam"]):
        return "countries", None

    # Gracias / despedida
    if any(w in t for w in ["gracias", "thanks", "chao", "adiós", "adios", "bye"]):
        return "thanks", None

    return "general", None


_RESPONSES: dict[str, list[str]] = {
    "greeting": [
        "¡Hola! 👋 Soy SofIA, asesora digital de Yastubo. Estoy aquí para ayudarte 24/7.\n\nSeguro has visto esas colectas y GoFundMe cuando alguien fallece lejos 😔 Con Yastubo eso se acaba.\n\n¿En qué puedo ayudarte hoy?",
        "¡Hola! 👋 Bienvenido(a). Soy SofIA de Yastubo. ¿Necesitas información sobre nuestra membresía o descargar un voucher?",
    ],
    "pricing": [
        "La membresía Yastubo tiene un precio único según tu domicilio:\n\n🇺🇸 **EE.UU.**: $14.99 USD/mes\n🌎 **LATAM**: $4.99 USD/mes\n\nEs menos que un café al mes y evita gastos de miles de dólares después. ¿Te gustaría suscribirte?",
    ],
    "info": [
        "Yastubo es una **Membresía de Asistencia Logística y Funeraria** pensada para latinos que viven lejos de su familia.\n\n✅ Si falleces en EE.UU.: coordinamos recuperación, documentación, preparación, flete aéreo y repatriación a tu país.\n\n✅ Si falleces en LATAM: funeral completo con nuestra red (levantamiento, cofre, velación, traslado y destino final).\n\nTodo coordinado para que tu familia no tenga que endeudarse ni improvisar. ¿Tienes alguna pregunta específica?",
    ],
    "coverage": [
        "La membresía incluye:\n\n**En EE.UU.:**\n• Recuperación y custodia del cuerpo\n• Documentación y permisos\n• Preparación técnica\n• Contenedor y aeropuerto\n• Flete aéreo\n• Cremación logística opcional\n\n**En LATAM:**\n• Funeral completo: levantamiento, preparación, cofre estándar, velación, traslado y destino final\n\n¿Necesitas más detalles sobre algún servicio?",
    ],
    "age": [
        "La política de edad es:\n\n• **Ingreso máximo**: 59 años y 364 días\n• Si ya estás dentro, puedes continuar **sin límite de edad** mientras estés al día con tu membresía\n\n¿Algo más en lo que pueda ayudarte?",
    ],
    "countries": [
        "Yastubo aplica para miembros con domicilio habitual en:\n\n🇺🇸 **Estados Unidos**\n🌎 **Países hispanohablantes de LATAM** (Colombia, México, Perú, Ecuador, Guatemala, Honduras, Venezuela, etc.)\n\n❌ No se prestan servicios hacia/desde Cuba.\n\n¿De qué país eres?",
    ],
    "ask_doc": [
        "¡Claro! Para buscar tu voucher necesito tu **número de documento**. ¿Me lo puedes compartir?",
        "Con gusto te ayudo a descargar tu certificado. Por favor, dime tu **número de documento** o **nombre completo**.",
    ],
    "thanks": [
        "¡Con mucho gusto! 😊 Si necesitas algo más, aquí estaré. Que tengas un excelente día. 💛",
        "¡De nada! Recuerda que estoy disponible 24/7. ¡Cuídate mucho! 💛",
    ],
    "general": [
        "Entiendo tu consulta. Te puedo ayudar con:\n\n📋 **Información** sobre la membresía Yastubo\n💰 **Precios** y planes\n📄 **Descargar voucher** o certificado\n🌎 **Cobertura** y países\n\n¿Qué te interesa?",
    ],
    "not_found": [
        "No encontré contratos activos con ese dato 😔. Verifica que el número de documento sea correcto o intenta con tu nombre completo.\n\nSi crees que hay un error, contacta a nuestro equipo: **+1 305 447 7669**",
    ],
    "found": [
        "¡Encontré tu información! 🎉 Aquí están tus contratos activos. Puedes descargar el PDF de cada uno:",
    ],
}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Chat con SofIA — respuestas inteligentes con búsqueda real de contratos."""
    if not body.messages:
        return ChatResponse(reply=_random.choice(_RESPONSES["greeting"]))

    last_msg = body.messages[-1].content
    intent, data = _detect_intent(last_msg)

    # Link de pago con referido
    if intent == "referral_link":
        from common.models.subscription import Subscription
        from common.models.user import User

        ref_code = None
        if data:
            # Buscar suscripción por nombre del usuario
            like = f"%{data}%"
            sub_stmt = (
                select(Subscription, User)
                .join(User, Subscription.user_id == User.id)
                .where(
                    Subscription.status == "active",
                    or_(
                        User.display_name.ilike(like),
                        User.first_name.ilike(like),
                        User.last_name.ilike(like),
                    ),
                )
                .limit(1)
            )
            row = (await db.execute(sub_stmt)).first()
            if row:
                sub, user = row
                ref_code = sub.referral_code

        if ref_code:
            import os
            stripe_link = None
            try:
                import stripe
                stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "") or getattr(settings, "stripe_secret_key", "")
                price_id = os.environ.get("STRIPE_PRICE_ID", "") or getattr(settings, "stripe_price_id", "")
                if stripe.api_key and price_id:
                    pl = stripe.PaymentLink.create(
                        line_items=[{"price": price_id, "quantity": 1}],
                        metadata={"referral_code": ref_code},
                    )
                    stripe_link = pl.url
            except Exception as exc:
                logger.warning("Stripe payment link error: %s", exc)

            if not stripe_link:
                base = settings.app_url.rstrip("/")
                stripe_link = f"{base}/customer/subscriptions?ref={ref_code}"

            reply = (
                f"¡Aquí tienes tu link de pago personalizado! 🎉\n\n"
                f"Compártelo con quien quieras invitar a Yastubo. "
                f"Cuando se suscriban, tú ganas **10% de comisión** ($1.50 USD/mes por cada referido activo).\n\n"
                f"Tu código: **{ref_code}**"
            )
            return ChatResponse(
                reply=reply,
                contracts=[{
                    "full_name": "Link de pago con tu referido",
                    "document_number": ref_code,
                    "status": "active",
                    "type": "Link de suscripción",
                    "pdf_url": stripe_link,
                }],
            )
        else:
            return ChatResponse(reply="Para generar tu link de pago primero necesitas tener una suscripción activa. ¿Te gustaría suscribirte?")

    # Si es búsqueda de documento o nombre, hacemos la búsqueda real
    if intent in ("search_doc", "search_name") and data:
        contracts = await _search_contracts(data, db)
        if contracts:
            reply = _random.choice(_RESPONSES["found"])
            return ChatResponse(reply=reply, contracts=contracts)
        else:
            return ChatResponse(reply=_random.choice(_RESPONSES["not_found"]))

    # Para el resto, respuestas mockeadas
    replies = _RESPONSES.get(intent, _RESPONSES["general"])
    return ChatResponse(reply=_random.choice(replies))

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
    import os
    base = os.environ.get("APP_PUBLIC_URL", "") or settings.app_url
    base = base.rstrip("/")
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
